#!/usr/bin/env python3
"""Compile the production probe with host stubs; never load a module."""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(__file__).resolve().with_name('q3_ram_window_probe.c')
stub = r'''
#ifndef MOCK_H
#define MOCK_H
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#define __init
#define __exit
#define MODULE_LICENSE(...)
#define MODULE_DESCRIPTION(...)
#define MODULE_PARM_DESC(...)
#define module_param_string(...)
#define module_init(...)
#define module_exit(...)
#define pr_info(...) ((void)0)
#define pr_err(...) ((void)0)
#define PAGE_SHIFT 12
#define pageblock_order 10
#define pageblock_nr_pages 1024UL
#define CONFIG_CMA 1
#define CONFIG_MEMORY_ISOLATION 1
#define IS_ENABLED(x) hotplug
enum { MIGRATE_UNMOVABLE, MIGRATE_MOVABLE, MIGRATE_RECLAIMABLE,
       MIGRATE_HIGHATOMIC, MIGRATE_CMA, MIGRATE_ISOLATE };
struct zone { const char *name; };
struct page { struct zone *zone; int type, reserved, device; };
static struct zone zones[2]={{"DMA"},{"Normal"}};
static struct page pages[13312];
static bool hotplug, board=true;
static unsigned long bad_pfn;
static int dereferences;
static int of_machine_is_compatible(const char *s) { (void)s; return board; }
static int pfn_valid(unsigned long pfn) { return pfn>=0x90000 && pfn<0x93400 && pfn!=bad_pfn; }
static struct page *pfn_to_page(unsigned long pfn) {
    assert(pfn_valid(pfn)); dereferences++; return &pages[pfn-0x90000];
}
static bool is_zone_device_page(struct page *p) { return p->device; }
static struct zone *page_zone(struct page *p) { return p->zone; }
static int get_pageblock_migratetype(struct page *p) { return p->type; }
static int PageReserved(struct page *p) { return p->reserved; }
static int scnprintf(char *dst, size_t n, const char *fmt, ...) {
    va_list args; va_start(args,fmt); int result=vsnprintf(dst,n,fmt,args); va_end(args);
    return result < 0 ? 0 : (result >= (int)n ? (int)n-1 : result);
}
#endif
'''
tests = r'''
int main(void) {
    for (unsigned i=0;i<13312;i++) {
        pages[i].zone=&zones[0]; pages[i].type=MIGRATE_MOVABLE;
    }
    hotplug=true;
    assert(q3_window_init()==-EOPNOTSUPP && dereferences==0);
    hotplug=false; board=false;
    assert(q3_window_init()==-ENODEV && dereferences==0);
    board=true; bad_pfn=0x90000;
    assert(q3_window_init()==-ERANGE && dereferences==0);
    bad_pfn=0; pages[0].device=1;
    assert(q3_window_init()==-ERANGE);
    pages[0].device=0;
    assert(q3_window_init()==0);
    assert(strstr(report,"sampled_uniform=1 movable_only=1 reserved=0"));
    assert(strstr(report,"atomic=0 owned=0 dma_safe=0"));
    pages[1024].type=MIGRATE_CMA; pages[100].reserved=1;
    pages[2048].zone=&zones[1];
    assert(q3_window_init()==0);
    assert(strstr(report,"sampled_uniform=0 movable_only=0 reserved=1"));
    assert(strstr(report,"summary same_zone=0"));
    assert(strstr(report,"allocation_feasible=unknown"));
    q3_window_exit();
    puts("PASS production metadata probe: hotplug/board refusal before PFN access, invalid/device PFNs, uniform/mixed blocks/zones, reserved pages; host mocks only");
}
'''
with tempfile.TemporaryDirectory(prefix='q3-memory-probe-') as temporary:
    root = Path(temporary)
    include = root / 'linux'
    include.mkdir()
    (root / 'mock.h').write_text(stub)
    for name in ['init', 'mm', 'mmzone', 'module', 'of', 'pageblock-flags']:
        (include / (name + '.h')).write_text('#include "mock.h"\n')
    (root / 'test.c').write_text('#include "' + str(source) + '"\n' + tests)
    subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I', str(root), str(root / 'test.c'), '-o', str(root / 'test')],
                   check=True, timeout=60)
    subprocess.run([str(root / 'test')], check=True, timeout=10)
