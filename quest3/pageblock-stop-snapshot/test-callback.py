#!/usr/bin/env python3
"""Compile the actual metadata callback with host mocks; no CPU pause or module load."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

source = Path(__file__).with_name('q3_pageblock_snapshot.c').read_text()
definitions = source[source.index('struct block_record {'):source.index('static struct snapshot snapshot;')]
callback = source[source.index('static int sample_heads('):source.index('static ssize_t report_show(')]
calls = set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', callback))
assert calls <= {'sample_heads', 'ktime_get_mono_fast_ns', 'irqs_disabled', 'if', 'for',
                 'pfn_to_online_page', 'is_zone_device_page', 'get_pageblock_migratetype',
                 'PageReserved', 'strscpy', 'page_zone', 'sizeof', 'pfn_valid'}, calls
assert source.index('if (!sample)') < source.index('ret = stop_machine(')
harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint64_t u64;
#define FIRST_PFN 0x90000UL
#define BLOCK_PAGES 1024UL
#define BLOCK_COUNT 13
#define CALLBACK_BUDGET_NS 1000000ULL
#define PAGE_SHIFT 12
struct zone { const char *name; } zone={"DMA"};
struct page { int type; bool reserved, device; struct zone *zone; } pages[13];
static bool irq=true;
static int missing=-1, reads;
static u64 now, step=50;
static u64 ktime_get_mono_fast_ns(void) { u64 result=now; now+=step; return result; }
static bool irqs_disabled(void) { return irq; }
static struct page *pfn_to_online_page(unsigned long pfn) {
    assert(pfn>=FIRST_PFN && (pfn-FIRST_PFN)%BLOCK_PAGES==0);
    unsigned long i=(pfn-FIRST_PFN)/BLOCK_PAGES;
    assert(i<13); reads++; return (int)i==missing ? NULL : &pages[i];
}
static bool is_zone_device_page(struct page *p) { return p->device; }
static int get_pageblock_migratetype(struct page *p) { return p->type; }
static bool PageReserved(struct page *p) { return p->reserved; }
static struct zone *page_zone(struct page *p) { return p->zone; }
static void strscpy(char *dst, const char *src, size_t size) { snprintf(dst,size,"%s",src); }
'''
tests = r'''
int main(void) {
    struct snapshot s={0};
    for(int i=0;i<13;i++) { pages[i].zone=&zone; pages[i].type=i%3; }
    irq=false;
    assert(sample_heads(&s)==-EPERM && reads==0);
    irq=true; missing=0;
    assert(sample_heads(&s)==-ERANGE && s.completed==0);
    missing=-1; pages[0].device=true;
    assert(sample_heads(&s)==-ERANGE && s.completed==0);
    pages[0].device=false; reads=0;
    assert(sample_heads(&s)==0 && s.completed==13 && reads==13);
    assert(s.duration_ns<=CALLBACK_BUDGET_NS);
    for(int i=0;i<13;i++) {
        assert(s.blocks[i].pfn==FIRST_PFN+(unsigned)i*BLOCK_PAGES);
        assert(s.blocks[i].type==i%3 && !strcmp(s.blocks[i].zone,"DMA"));
    }
    memset(&s,0,sizeof(s)); missing=7;
    assert(sample_heads(&s)==-ERANGE && s.completed==7);
    memset(&s,0,sizeof(s)); missing=-1; step=2000000; reads=0;
    assert(sample_heads(&s)==-ETIMEDOUT && s.completed==0 && reads==0);
    puts("PASS actual stop callback: IRQ guard, 13 fixed head samples, offline/device refusal, partial failure and callback budget; mocks do not validate stop_machine or firmware");
}
'''
with tempfile.TemporaryDirectory(prefix='q3-stop-snapshot-') as temporary:
    folder = Path(temporary)
    (folder / 'test.c').write_text(harness + definitions + callback + tests)
    subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    str(folder / 'test.c'), '-o', str(folder / 'test')], check=True, timeout=60)
    subprocess.run([str(folder / 'test')], check=True, timeout=10)
