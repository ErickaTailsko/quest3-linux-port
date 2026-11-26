#!/usr/bin/env python3
"""Compile actual lookup/validation bodies with host mocks; never loads a module."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

folder = Path(__file__).resolve().parent
source = (folder/'q3_reserved_descriptors.c').read_text()
definitions = source[source.index('struct expected_region {'):source.index('static struct region_record records')]
functions = source[source.index('static int validate_record('):source.index('static ssize_t report_show(')]
show = source[source.index('static ssize_t report_show('):source.index('static struct kobj_attribute report_attr')]
assert 'query_one(' not in show and 'of_reserved_mem_lookup' not in show
assert source.index('if (!inspect)') < source.index('records[i].error = query_one(')
for forbidden in ['stop_machine(', 'alloc_contig_range(', 'pfn_valid(', 'phys_to_virt(', 'kallsyms', 'kprobe', '->device_init(', '->device_release(']:
    assert forbidden not in source
calls = set(re.findall(r'\b([a-zA-Z_]\w*)\s*\(', functions))
assert calls <= {'validate_record','query_one','if','sizeof','scnprintf','of_find_node_by_path',
                 'of_device_is_available','of_device_is_compatible','of_property_read_bool',
                 'of_property_read_u64','of_reserved_mem_lookup','strcmp','READ_ONCE','of_node_put'}, calls
inventory = json.loads((folder.parent/'restart-backend-design/dynamic-reservation-inventory.json').read_text())
for entry in inventory['entries']:
    name = entry['node'].rsplit('/',1)[-1]
    assert ('"'+name+'"') in definitions
harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint64_t u64;
#define U64_MAX UINT64_MAX
#define READ_ONCE(x) (x)
#define scnprintf snprintf
struct device_node { int unused; } node;
struct reserved_mem { const char *name; u64 base, size; void *ops, *priv; } rmem;
static int missing_node, missing_region, puts_count, lookups;
static bool available=true, reusable=true, nomap=false;
static u64 requested;
static struct device_node *of_find_node_by_path(const char *p) {
    assert(!strncmp(p,"/reserved-memory/",17)); return missing_node ? NULL : &node;
}
static bool of_device_is_available(struct device_node *n) { assert(n==&node); return available; }
static bool of_device_is_compatible(struct device_node *n,const char *c) {
    assert(n==&node && !strcmp(c,"shared-dma-pool")); return true;
}
static bool of_property_read_bool(struct device_node *n,const char *k) {
    assert(n==&node);return !strcmp(k,"reusable") ? reusable : nomap;
}
static int of_property_read_u64(struct device_node *n,const char *k,u64 *v) {
    assert(n==&node && !strcmp(k,"size"));*v=requested;return 0;
}
static struct reserved_mem *of_reserved_mem_lookup(struct device_node *n) {
    assert(n==&node);lookups++;return missing_region ? NULL : &rmem;
}
static void of_node_put(struct device_node *n) { assert(n==&node);puts_count++; }
'''
tests = r'''
int main(void) {
    struct region_record record={0};
    for (unsigned i=0;i<13;i++) {
        const struct expected_region *s=&expected[i];
        requested=s->size;
        rmem=(struct reserved_mem){s->name,s->lower ? s->lower : 0x80000000ULL,s->size,(void*)1,(void*)1};
        memset(&record,0,sizeof(record));
        assert(query_one(s,&record)==0 && record.size==s->size && record.ops_present && record.priv_present);
    }
    assert(lookups==13 && puts_count==13);
    const struct expected_region *s=&expected[0];requested=s->size;
    rmem=(struct reserved_mem){s->name,0x80000000ULL,s->size,(void*)1,(void*)1};
    missing_node=1;assert(query_one(s,&record)==-ENOENT && puts_count==13);missing_node=0;
    missing_region=1;assert(query_one(s,&record)==-ENOENT);missing_region=0;
    requested=1;int old=lookups;assert(query_one(s,&record)==-EINVAL && old==lookups);requested=s->size;
    reusable=false;assert(query_one(s,&record)==-EINVAL);reusable=true;
    nomap=true;assert(query_one(s,&record)==-EINVAL);nomap=false;
    available=false;assert(query_one(s,&record)==-EINVAL);available=true;
    rmem.name="wrong";assert(query_one(s,&record)==-EINVAL);rmem.name=s->name;
    rmem.ops=NULL;assert(query_one(s,&record)==-EINVAL);rmem.ops=(void*)1;
    rmem.priv=NULL;assert(query_one(s,&record)==-EINVAL);rmem.priv=(void*)1;
    rmem.base=0;assert(query_one(s,&record)==-EINVAL);
    rmem.base=0x80000001ULL;assert(query_one(s,&record)==-ERANGE);
    rmem.base=0x100000000ULL;assert(query_one(s,&record)==-ERANGE);
    record=(struct region_record){0xfffffffffe000000ULL,s->size,true,true,0};
    assert(validate_record(s,&record)==-ERANGE);
    puts("PASS actual descriptor query: 13 names, high addresses, node release, missing/failed setup, constraints and overflow; mocks only");
}
'''
with tempfile.TemporaryDirectory(prefix='q3-reserved-query-') as tmp:
    p=Path(tmp);(p/'test.c').write_text(harness+definitions+functions+tests)
    subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True,timeout=60)
    subprocess.run([str(p/'test')],check=True,timeout=10)
