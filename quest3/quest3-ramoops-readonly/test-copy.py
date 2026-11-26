#!/usr/bin/env python3
"""Production C mapping/read functions with simulated reserved pages; no hardware."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent
source = (root / 'q3_ramoops_snapshot.c').read_text()
read = source[source.index('static ssize_t q3_snapshot_read'):source.index('static struct bin_attribute')]
copy = source[source.index('static int q3_copy_region'):source.index('static int __init')]
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#define __iomem
#define loff_t long long
typedef uint64_t phys_addr_t;
#define PAGE_SHIFT 12
#define PHYS_PFN(x) ((x)>>PAGE_SHIFT)
#define PAGE_KERNEL 0
#define GFP_KERNEL 0
#define VM_MAP 1
#define VM_IOREMAP 2
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
struct file {}; struct kobject {}; struct bin_attribute {};
struct page {bool reserved;};
static struct page pages[2];
static bool valid[2];static int fail_alloc,fail_map,unmaps,maps;
static unsigned char raw[8192],destination[8192];
static void *snapshot=destination;static size_t snapshot_size=sizeof(raw);
static int pfn_valid(unsigned long pfn) {assert(pfn>=256&&pfn<258);return valid[pfn-256];}
static struct page *pfn_to_page(unsigned long pfn) {assert(pfn>=256&&pfn<258);return &pages[pfn-256];}
#define PageReserved(p) ((p)->reserved)
static void *kmalloc_array(size_t n,size_t size,int flags) {(void)flags;return fail_alloc?NULL:malloc(n*size);}
static void kfree(void *p) {free(p);}
static int pgprot_writecombine(int prot) {assert(!prot);return 99;}
static void *vmap(struct page **list,unsigned int count,int flags,int prot) {
 assert(list[0]==&pages[0]&&list[1]==&pages[1]);assert(count==2&&flags==3&&prot==99);
 maps++;return fail_map?NULL:raw;
}
static void vunmap(void *p) {assert(p==raw);unmaps++;}
static void *ioremap_wc(phys_addr_t start,size_t size) {
 assert(start==0x100000&&size==sizeof(raw));maps++;return fail_map?NULL:raw;
}
static void iounmap(void *p) {assert(p==raw);unmaps++;}
static void memcpy_fromio(void *dest,const void *src,size_t size) {
 assert(dest==destination&&src==raw&&size==sizeof(raw));memcpy(dest,src,size);
}
'''
main = r'''
int main(void) {
 unsigned char before[sizeof(raw)],out[sizeof(raw)];size_t i;
 for(i=0;i<sizeof(raw);i++)raw[i]=(i*17)&255;
 memcpy(before,raw,sizeof(raw));
 valid[0]=valid[1]=true;pages[0].reserved=pages[1].reserved=true;
 assert(!q3_copy_region(0x100000,sizeof(raw)));
 assert(!memcmp(raw,before,sizeof(raw))&&!memcmp(destination,raw,sizeof(raw)));
 assert(maps==1&&unmaps==1);
 assert(q3_snapshot_read(0,0,0,(char *)out,-1,1)==-EINVAL);
 assert(q3_snapshot_read(0,0,0,(char *)out,sizeof(raw),1)==0);
 assert(q3_snapshot_read(0,0,0,(char *)out,sizeof(raw)+1,1)==0);
 assert(q3_snapshot_read(0,0,0,(char *)out,8190,sizeof(out))==2);
 assert(!memcmp(out,raw+8190,2));
 pages[1].reserved=false;assert(q3_copy_region(0x100000,sizeof(raw))==-EPERM);
 pages[1].reserved=true;valid[1]=false;assert(q3_copy_region(0x100000,sizeof(raw))==-EINVAL);
 valid[1]=true;fail_alloc=1;assert(q3_copy_region(0x100000,sizeof(raw))==-ENOMEM);
 fail_alloc=0;fail_map=1;assert(q3_copy_region(0x100000,sizeof(raw))==-ENOMEM);
 valid[0]=valid[1]=false;assert(q3_copy_region(0x100000,sizeof(raw))==-ENOMEM);
 fail_map=0;assert(!q3_copy_region(0x100000,sizeof(raw)));
 assert(!memcmp(raw,before,sizeof(raw))&&!memcmp(destination,raw,sizeof(raw)));
 puts("PASS production C read bounds, reserved/mixed PFN guards, both mapping paths, failure returns and original bytes unchanged");
}
'''
with tempfile.TemporaryDirectory() as temp:
    c = Path(temp) / 'test.c'; binary = Path(temp) / 'test'
    c.write_text(prefix + read + copy + main)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-Wno-sign-compare', '-fsanitize=undefined', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
