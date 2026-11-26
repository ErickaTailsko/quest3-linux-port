#!/usr/bin/env python3
"""Compile actual query/init/exit/report bodies with host mocks; no module build/load."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

source = Path(__file__).with_name('q3_cma_identity.c').read_text()
body = source[source.index('struct identity_record {'):source.index('module_init(')]
query = source[source.index('static int query_identity('):source.index('static ssize_t report_show(')]
show = source[source.index('static ssize_t report_show('):source.index('static struct kobj_attribute report_attr')]
assert 'query_identity(' not in show and 'cma_get_name(' not in show
assert 'area->' not in source
for forbidden in ('cma_alloc(', 'cma_release(', 'alloc_pages', 'alloc_contig', 'stop_machine(',
                  'pfn_valid(', 'phys_to_virt(', 'kallsyms', 'kprobe', '->device_init(', '->device_release('):
    assert forbidden not in source
calls = set(re.findall(r'\b([a-zA-Z_]\w*)\s*\(', query))
assert calls <= {'query_identity', 'if', 'sizeof', 'READ_ONCE', 'strncmp',
                 'of_find_node_by_path', 'of_device_is_available', 'of_device_is_compatible',
                 'of_property_read_bool', 'of_property_read_u64', 'of_reserved_mem_lookup',
                 'of_node_put', 'cma_get_name'}, calls
assert source.index('if (!inspect)') < source.index('error = query_identity(')
assert source.index('READ_ONCE(rmem->priv) != area') < source.index('name = cma_get_name(area)')
assert 'static_assert(sizeof(struct reserved_mem) == 56)' in source

harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
typedef uint64_t u64;
#define READ_ONCE(x) (x)
#define __init
#define __exit
#define PAGE_SHIFT 12
#define module_param(a,b,c)
#define module_param_string(a,b,c,d)
#define MODULE_PARM_DESC(a,b)
#define __ATTR(a,b,c,d) { .attr=0, .show=c }
#define sysfs_emit snprintf_emit
struct device_node { int unused; } node;
struct cma { int unused; } area_object, other_area;
struct reserved_mem { const char *name; u64 base,size; void *ops,*priv; } rmem;
struct kobject { int unused; } object;
struct kobject *kernel_kobj=&object;
struct kobj_attribute { int attr; ssize_t (*show)(struct kobject *,struct kobj_attribute *,char *); };
static struct cma *dma_contiguous_default_area;
static int puts_count,lookups,names,created,destroyed,removed;
static bool missing_node,missing_region,available,compatible,reusable,nomap,default_prop;
static bool property_error,machine,create_fail,file_fail,change_default,change_priv;
static u64 requested;
static const char *area_name;
static struct device_node *of_find_node_by_path(const char *p) {
    assert(!strcmp(p,"/reserved-memory/linux,cma"));return missing_node ? NULL : &node;
}
static bool of_device_is_available(struct device_node *n) { assert(n==&node);return available; }
static bool of_device_is_compatible(struct device_node *n,const char *s) {
    assert(n==&node && !strcmp(s,"shared-dma-pool"));return compatible;
}
static bool of_property_read_bool(struct device_node *n,const char *s) {
    assert(n==&node);
    if (!strcmp(s,"reusable")) return reusable;
    if (!strcmp(s,"linux,cma-default")) return default_prop;
    assert(!strcmp(s,"no-map"));return nomap;
}
static int of_property_read_u64(struct device_node *n,const char *s,u64 *v) {
    assert(n==&node && !strcmp(s,"size"));*v=requested;return property_error ? -EINVAL : 0;
}
static struct reserved_mem *of_reserved_mem_lookup(struct device_node *n) {
    assert(n==&node);lookups++;return missing_region ? NULL : &rmem;
}
static void of_node_put(struct device_node *n) { assert(n==&node);puts_count++; }
static const char *cma_get_name(const struct cma *a) {
    assert(a==&area_object && rmem.priv==a);names++;
    if (change_default) dma_contiguous_default_area=&other_area;
    if (change_priv) rmem.priv=&other_area;
    return area_name;
}
static bool of_machine_is_compatible(const char *s) {
    assert(!strcmp(s,"qcom,anorak") || !strcmp(s,"oculus,eureka"));return machine;
}
static struct kobject *kobject_create_and_add(const char *s,struct kobject *p) {
    assert(!strcmp(s,"q3_cma_identity") && p==kernel_kobj);created++;return create_fail ? NULL : &object;
}
static void kobject_put(struct kobject *p) { assert(p==&object);destroyed++; }
static int sysfs_create_file(struct kobject *p,const int *a) {
    assert(p==&object && a);return file_fail ? -ENOMEM : 0;
}
static void sysfs_remove_file(struct kobject *p,const int *a) { assert(p==&object && a);removed++; }
static int snprintf_emit(char *buffer,const char *fmt,const char *s) { return snprintf(buffer,4096,fmt,s); }
'''
tests = r'''
static void reset(void) {
    record=(struct identity_record){0};memset(report,0,sizeof(report));report_kobj=NULL;
    puts_count=lookups=names=created=destroyed=removed=0;
    missing_node=missing_region=nomap=property_error=create_fail=file_fail=change_default=change_priv=false;
    available=compatible=reusable=default_prop=machine=inspect=true;
    requested=32ULL*1024*1024;area_name="linux,cma";
    rmem=(struct reserved_mem){"linux,cma",0x40000000ULL,requested,&object,&area_object};
    dma_contiguous_default_area=&area_object;
    strcpy(attempt,"0123456789abcdef0123456789abcdef");
}
static void rejected(unsigned stage,int accessors) {
    assert(query_identity(&record)<0 && record.stage==stage && !record.stable);
    assert(puts_count==(!missing_node) && names==accessors);
}
int main(void) {
    reset();assert(!query_identity(&record) && record.stage==7 && record.stable && names==1 && puts_count==1);
    reset();missing_node=true;rejected(1,0);assert(!lookups);
    reset();available=false;rejected(2,0);assert(!lookups);
    reset();compatible=false;rejected(2,0);
    reset();reusable=false;rejected(2,0);
    reset();default_prop=false;rejected(2,0);
    reset();nomap=true;rejected(2,0);
    reset();property_error=true;rejected(2,0);
    reset();requested=1;rejected(2,0);
    reset();missing_region=true;rejected(3,0);
    reset();rmem.name=NULL;rejected(3,0);
    reset();rmem.name="linux,cma-other";rejected(3,0);
    reset();rmem.ops=NULL;rejected(3,0);
    reset();rmem.size=1;rejected(3,0);
    reset();rmem.base=0;rejected(3,0);
    reset();rmem.base=0x40001000ULL;rejected(3,0);
    reset();rmem.base=(1ULL<<32)-4*1024*1024;rejected(3,0);
    reset();rmem.base=UINT64_MAX-4*1024*1024+1;rejected(3,0);
    reset();rmem.base=(1ULL<<32)-requested;assert(!query_identity(&record));
    reset();dma_contiguous_default_area=NULL;rejected(4,0);
    reset();rmem.priv=NULL;rejected(4,0);
    reset();rmem.priv=&other_area;rejected(4,0);
    reset();area_name=NULL;rejected(5,1);
    reset();area_name="linux,cma-extra";rejected(5,1);
    reset();change_default=true;rejected(6,1);
    reset();change_priv=true;rejected(6,1);
    reset();inspect=false;assert(q3_identity_init()==-EACCES && !lookups && !created);
    reset();attempt[0]=0;assert(q3_identity_init()==-EINVAL && !lookups);
    reset();attempt[0]='G';assert(q3_identity_init()==-EINVAL && !lookups);
    reset();machine=false;assert(q3_identity_init()==-ENODEV && !lookups);
    reset();create_fail=true;assert(q3_identity_init()==-ENOMEM && puts_count==1 && !destroyed);
    reset();file_fail=true;assert(q3_identity_init()==-ENOMEM && destroyed==1 && !report_kobj);
    reset();assert(!q3_identity_init());
    char buffer[4096];assert(report_show(NULL,NULL,buffer)>0 && !strcmp(buffer,report));
    assert(strstr(report,"identity_observed=1 error=0 stage=7") && strstr(report,"allocator_called=0"));
    assert(names==1 && lookups==1);report_show(NULL,NULL,buffer);assert(names==1 && lookups==1);
    q3_identity_exit();assert(removed==1 && destroyed==1);
    reset();rmem.priv=&other_area;assert(!q3_identity_init());
    assert(strstr(report,"identity_observed=0 error=-22 stage=4") && !names);
    q3_identity_exit();assert(removed==1 && destroyed==1);
    puts("PASS actual identity C bodies: gates, properties, bounds, pointer-before-name, recheck, OF/sysfs cleanup; mocks only");
}
'''
with tempfile.TemporaryDirectory(prefix='q3-cma-identity-') as temporary:
    root = Path(temporary)
    (root/'test.c').write_text(harness + body + tests)
    subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    str(root/'test.c'), '-o', str(root/'test')], check=True, timeout=60)
    subprocess.run([str(root/'test')], check=True, timeout=10)
