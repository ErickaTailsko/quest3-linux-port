#!/usr/bin/env python3
"""Compile reviewed vendor/resource bodies with mocks; never calls a real kernel."""
import os
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

fixture = Path(__file__).with_name('mem-buf-range-extracts.h').read_text()
audit = json.loads(Path(__file__).with_name('mem-buf-range-audit.json').read_text())
assert hashlib.sha256(fixture.encode()).hexdigest() == audit['fixture_sha256']
assert all(entry['fixture_matches_source_ignoring_only_comments_and_whitespace']
           for entry in audit['reviewed_function_extracts'].values())
harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
typedef uint64_t u64;
typedef uint64_t resource_size_t;
struct resource {
    resource_size_t start,end;
    unsigned long flags,desc;
    const char *name;
    struct resource *parent,*child,*sibling;
};
#define IORESOURCE_MEM 0x200UL
#define IORESOURCE_SYSTEM_RAM (IORESOURCE_MEM | 0x1000000UL)
#define IORESOURCE_BUSY 0x80000000UL
#define IORESOURCE_MUXED 0x400000UL
#define IORES_DESC_DEVICE_PRIVATE_MEMORY 2UL
#define GFP_KERNEL 0
#define TASK_UNINTERRUPTIBLE 0
#define current 0
#define DECLARE_WAITQUEUE(name, task) int name = (task)
#define pr_warn(...) do {} while (0)
#define pr_err(...) do {} while (0)
static int resource_lock,muxed_resource_wait;
static struct resource iomem_resource,boot;
static struct resource *alloc_resource(int flags) { (void)flags; return calloc(1,sizeof(struct resource)); }
static void free_resource(struct resource *r) { free(r); }
static unsigned long resource_type(struct resource *r) { return r->flags & IORESOURCE_MEM; }
static unsigned long resource_ext_type(struct resource *r) { (void)r; return 0; }
static void write_lock(int *lock) { assert(!*lock);*lock=1; }
static void write_unlock(int *lock) { assert(*lock);*lock=0; }
static void revoke_devmem(struct resource *r) { assert(r); }
static void add_wait_queue(int *q,int *w) { (void)q;(void)w;assert(0); }
static void remove_wait_queue(int *q,int *w) { (void)q;(void)w;assert(0); }
static void set_current_state(int s) { (void)s;assert(0); }
static void schedule(void) { assert(0); }
struct gh_sgl_desc { uint16_t n_sgl_entries; struct { u64 ipa_base,size; } sgl_entries[3]; };
static int add_memory_subsection(int nid,u64 base,u64 size);
static int remove_memory_subsection(int nid,u64 base,u64 size);
static int numa_node_id(void) { return 0; }
'''
tests = r'''
static u64 removed[3],failed_remove;
static unsigned added_calls,removed_calls;
static int add_memory_subsection(int nid,u64 base,u64 size) {
    assert(nid==0);added_calls++;
    if ((base | size) & ((1ULL<<21)-1)) return -EINVAL;
    /* Resource-registration part only; no real arch_add_memory/memblock. */
    return __request_region(&iomem_resource,base,size,"System RAM",
        IORESOURCE_SYSTEM_RAM | IORESOURCE_BUSY) ? 0 : -EEXIST;
}
static int remove_memory_subsection(int nid,u64 base,u64 size) {
    assert(nid==0 && size && removed_calls<3);
    removed[removed_calls++]=base;
    /* Record only: never dereference or remove actual memory. */
    return base==failed_remove ? -EBUSY : 0;
}
static void reset(bool busy) {
    iomem_resource=(struct resource){.start=0,.end=UINT64_MAX,.flags=IORESOURCE_MEM};
    boot=(struct resource){.start=0x90000000ULL,.end=0x933fffffULL,
        .flags=IORESOURCE_SYSTEM_RAM | (busy ? IORESOURCE_BUSY : 0),.name="System RAM"};
    iomem_resource.child=&boot;boot.parent=&iomem_resource;
    added_calls=removed_calls=0;failed_remove=UINT64_MAX;
}
int main(void) {
    struct gh_sgl_desc s={.n_sgl_entries=1,.sgl_entries={{0x90000000ULL,1ULL<<21}}};
    reset(true);
    assert(mem_buf_map_mem_s1(&s)==-EEXIST && added_calls==1 && removed_calls==0);
    reset(false);
    assert(mem_buf_map_mem_s1(&s)==0); /* Name alone is not the BUSY flag. */
    assert(boot.child && boot.child->parent==&boot);
    reset(true);
    s.n_sgl_entries=2;s.sgl_entries[0].ipa_base=0x1000000000ULL;
    s.sgl_entries[1].ipa_base=0x90000000ULL;s.sgl_entries[1].size=1ULL<<21;
    assert(mem_buf_map_mem_s1(&s)==-EEXIST && added_calls==2 && removed_calls==1);
    assert(removed[0]==0x1000000000ULL); /* Rollback prefix, not failed entry. */
    reset(true);
    s.n_sgl_entries=3;s.sgl_entries[0].ipa_base=0x1000000000ULL;
    s.sgl_entries[1].ipa_base=0x1000200000ULL;s.sgl_entries[1].size=1ULL<<21;
    s.sgl_entries[2].ipa_base=0x90000000ULL;s.sgl_entries[2].size=1ULL<<21;
    failed_remove=s.sgl_entries[1].ipa_base;
    assert(mem_buf_map_mem_s1(&s)==-EEXIST && removed_calls==2);
    assert(removed[0]==0x1000200000ULL && removed[1]==0x1000000000ULL);
    /* Rollback continues after removal failure; return is original add error. */
    reset(true);
    s.n_sgl_entries=1;s.sgl_entries[0].ipa_base=0x93400000ULL;
    assert(mem_buf_map_mem_s1(&s)==0); /* Adjacent does not overlap. */
    reset(true);
    s.sgl_entries[0].ipa_base=0x8fe00000ULL;s.sgl_entries[0].size=2ULL<<21;
    assert(mem_buf_map_mem_s1(&s)==-EEXIST); /* Partial overlap is blocked. */
    reset(true);
    s.sgl_entries[0].ipa_base=0xffffffffffe00000ULL;s.sgl_entries[0].size=2ULL<<21;
    assert(mem_buf_map_mem_s1(&s)==-EEXIST); /* Wrapped inclusive end rejected. */
    reset(true);
    s.n_sgl_entries=2;s.sgl_entries[0].ipa_base=0x90000000ULL;s.sgl_entries[0].size=1ULL<<21;
    s.sgl_entries[1].ipa_base=0x1000000000ULL;s.sgl_entries[1].size=1ULL<<21;
    failed_remove=s.sgl_entries[0].ipa_base;
    assert(mem_buf_unmap_mem_s1(&s)==0 && removed_calls==2);
    assert(removed[0]==0x90000000ULL && removed[1]==0x1000000000ULL);
    /* This proves forwarding/no wrapper ownership guard and last-result
     * behavior, not that a valid userspace transaction can remove boot RAM. */
    puts("PASS reviewed mem_buf/resource bodies: BUSY conflict, nonbusy descent, 64-bit ranges, adjacency, overlap, wrap, prefix-only rollback, unmap forwarding and last-result semantics; mocks only");
}
'''
with tempfile.TemporaryDirectory(prefix='q3-mem-buf-ranges-',
                                 dir='/tmp/opencode' if Path('/tmp/opencode').is_dir() else None) as temporary:
    p=Path(temporary);(p/'test.c').write_text(harness+fixture+tests)
    subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-Wall','-Wextra','-Werror',
                    str(p/'test.c'),'-o',str(p/'test')],check=True,timeout=60)
    subprocess.run([str(p/'test')],check=True,timeout=10)
