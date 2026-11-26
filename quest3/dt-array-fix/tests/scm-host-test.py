#!/usr/bin/env python3
"""Exercise the production SCM implementation with fake DT and firmware I/O."""
from pathlib import Path
import os, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
source = '\n'.join(line for line in (root/'module/quest3-scm.c').read_text().splitlines() if not line.startswith('#include'))
shim = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint64_t phys_addr_t;
typedef uint32_t u32;
#define BIT(n) (1U << (n))
#define GFP_KERNEL 0
#define nr_cpu_ids 6
static int possible_cpus=2;
#define num_possible_cpus() (possible_cpus)
#define for_each_possible_cpu(cpu) for ((cpu)=0; (cpu)<possible_cpus; (cpu)++)
#define cpu_possible(cpu) ((cpu)>=0 && (cpu)<possible_cpus)
#define kcalloc(n,s,f) calloc(n,s)
#define kfree free
#define pr_info(...) do {} while (0)
#define pr_err(...) do { errors++; } while (0)
struct device_node { int id; } node, cpus[3];
struct of_phandle_args { struct device_node *np; u32 args[2]; };
static bool ready, present, enabled;
static int cells, entries[2], refs, reads, writes, errors, parse_fail;
static int fail_read, fail_write, mismatch, secure_calls, secure_result;
static bool rollback_fail;
static u32 addresses[6], values[6], thresholds[6];
static bool legacy;
static int legacy_count, threshold_count, property_fail;
static bool qcom_scm_is_available(void) { return ready; }
static int qcom_scm_sec_wdog_deactivate(void) { secure_calls++; return secure_result; }
static struct device_node *of_find_compatible_node(void *a, void *b, const char *s) {
 assert(!strcmp(s,"qcom,core-hang-detect")); if(!present) return NULL; refs++; return &node;
}
static bool of_device_is_available(struct device_node *n) { return enabled; }
static int of_property_count_u32_elems(struct device_node *n, const char *p) {
 if(!strcmp(p,"qcom,config-arr")) return legacy_count;
 if(!strcmp(p,"qcom,threshold-arr")) return threshold_count;
 assert(!strcmp(p,"qcom,chd-percpu-info")); return cells;
}
static void *of_find_property(struct device_node *n,const char *p,void *length) {
 assert(!strcmp(p,"qcom,chd-percpu-info")); return legacy?NULL:n;
}
static int of_property_read_u32_index(struct device_node *n,const char *p,int i,u32 *v) {
 assert(i>=0 && i<6); if(i==property_fail) return -EINVAL;
 if(!strcmp(p,"qcom,config-arr")) *v=addresses[i];
 else { assert(!strcmp(p,"qcom,threshold-arr")); *v=thresholds[i]; }
 return 0;
}
static int of_parse_phandle_with_fixed_args(struct device_node *n, const char *p,int count,int i,struct of_phandle_args *a) {
 assert(count==2 && i<2); if(i==parse_fail) return -EINVAL;
 a->np=&cpus[entries[i]]; a->args[0]=0x1234; a->args[1]=addresses[i]; refs++; return 0;
}
static int of_cpu_node_to_id(struct device_node *n) { return n->id; }
static void of_node_put(struct device_node *n) { assert(n); refs--; }
static int slot(phys_addr_t a) { for(int i=0;i<6;i++) if(addresses[i]==a) return i; assert(0); return 0; }
static int qcom_scm_io_readl(phys_addr_t a, u32 *v) {
 reads++; if(reads==fail_read) return -EACCES; *v=values[slot(a)];
 if(reads==mismatch) *v ^= BIT(7); return 0;
}
static int qcom_scm_io_writel(phys_addr_t a, u32 v) {
 writes++; values[slot(a)]=v; /* A failing call may have changed hardware. */
 if(writes==fail_write || (rollback_fail && writes>fail_write)) return -EIO; return 0;
}
static void reset(void) {
 possible_cpus=2; legacy=false; legacy_count=threshold_count=2; property_fail=-1;
 for(int i=0;i<6;i++) { addresses[i]=0x80000000+0x1000*i; thresholds[i]=addresses[i]-8; values[i]=0xa7; }
 ready=present=enabled=true; rollback_fail=false; cells=6; entries[0]=1; entries[1]=0;
 cpus[0].id=0; cpus[1].id=1; cpus[2].id=2;
 addresses[0]=0xabcdef00; addresses[1]=0x12345600; values[0]=0xa7; values[1]=0xb2;
 refs=reads=writes=errors=secure_calls=secure_result=0;
 parse_fail=fail_read=fail_write=mismatch=-1;
}
'''
tests = r'''
int main(void) {
 reset(); assert(qkx_core_hang_configure(0)==0 && !reads && !writes);
 assert(qkx_core_hang_configure(3)==-EINVAL && !reads);
 ready=false; assert(qkx_core_hang_configure(1)==-ENODEV && !refs);
 reset(); present=false; assert(qkx_core_hang_configure(1)==-ENODEV && !refs);
 reset(); enabled=false; assert(qkx_core_hang_configure(1)==-ENODEV && !refs);
 reset(); cells=5; assert(qkx_core_hang_configure(2)==-EINVAL && !reads && !refs);
 reset(); parse_fail=1; assert(qkx_core_hang_configure(2)==-EINVAL && !reads && !refs);
 reset(); entries[1]=1; assert(qkx_core_hang_configure(2)==-EINVAL && !reads && !refs);
 reset(); entries[1]=2; assert(qkx_core_hang_configure(2)==-EINVAL && !reads && !refs);
 reset(); addresses[1]=addresses[0]; assert(qkx_core_hang_configure(2)==-EINVAL && !reads && !refs);
 reset(); addresses[1]|=1; assert(qkx_core_hang_configure(2)==-EINVAL && !reads && !refs);
 reset(); addresses[1]=0; assert(qkx_core_hang_configure(2)==-EINVAL && !reads && !refs);
 reset(); assert(qkx_core_hang_configure(1)==0 && reads==2 && !writes && !refs);
 reset(); fail_read=2; assert(qkx_core_hang_configure(2)==-EACCES && !writes && !refs);
 reset(); assert(qkx_core_hang_configure(2)==0 && values[0]==0xa5 && values[1]==0xb0 && writes==2 && !refs);
 reset(); values[0]&=~BIT(1); assert(qkx_core_hang_configure(2)==0 && writes==1 && !refs);
 reset(); fail_write=2; assert(qkx_core_hang_configure(2)==-EIO && values[0]==0xa7 && values[1]==0xb2 && writes==4 && !refs);
 reset(); fail_read=4; assert(qkx_core_hang_configure(2)==-EACCES && values[0]==0xa7 && values[1]==0xb2 && !refs);
 reset(); mismatch=3; assert(qkx_core_hang_configure(2)==-EIO && values[0]==0xa7 && values[1]==0xb2 && !refs);
 reset(); fail_write=2; rollback_fail=true; assert(qkx_core_hang_configure(2)==-EIO && errors==2 && !refs);
 reset(); legacy=true; assert(qkx_core_hang_configure(1)==0 && reads==2 && !writes && !refs);
 reset(); legacy=true; assert(qkx_core_hang_configure(2)==-EOPNOTSUPP && !reads && !writes && !refs);
 reset(); legacy=true; legacy_count=0; assert(qkx_core_hang_configure(1)==-EINVAL && !reads && !refs);
 reset(); legacy=true; threshold_count=1; assert(qkx_core_hang_configure(1)==-EINVAL && !reads && !refs);
 reset(); legacy=true; possible_cpus=3; assert(qkx_core_hang_configure(1)==-EINVAL && !reads && !refs);
 reset(); legacy=true; addresses[1]=addresses[0]; assert(qkx_core_hang_configure(1)==-EINVAL && !reads && !refs);
 reset(); legacy=true; addresses[1]|=1; assert(qkx_core_hang_configure(1)==-EINVAL && !reads && !refs);
 reset(); legacy=true; thresholds[1]=0; assert(qkx_core_hang_configure(1)==-EINVAL && !reads && !refs);
 reset(); legacy=true; property_fail=1; assert(qkx_core_hang_configure(1)==-EINVAL && !reads && !refs);
 reset(); legacy=true; fail_read=2; assert(qkx_core_hang_configure(1)==-EACCES && reads==2 && !writes && !refs);
 reset(); legacy=true; possible_cpus=legacy_count=threshold_count=6;
 assert(qkx_core_hang_configure(1)==0 && reads==6 && !writes && !refs);
 reset(); cells=5; legacy_count=2; assert(qkx_core_hang_configure(1)==-EINVAL && !reads && !refs);
 puts("PASS: config-arr schema, six register entries, complete validation before reads, no fallback on malformed phandles, legacy writes rejected");
 reset(); assert(qkx_secure_watchdog_configure(0)==0 && !secure_calls);
 assert(qkx_secure_watchdog_configure(3)==-EINVAL && !secure_calls);
 assert(qkx_secure_watchdog_configure(1)==0 && !secure_calls);
 ready=false; assert(qkx_secure_watchdog_configure(2)==-ENODEV && !secure_calls);
 ready=true; secure_result=-EOPNOTSUPP; assert(qkx_secure_watchdog_configure(2)==-EOPNOTSUPP && secure_calls==1);
 secure_result=0; assert(qkx_secure_watchdog_configure(2)==0 && secure_calls==2);
 puts("PASS: DT validation/reference cleanup, read-only mode, exact bit update, I/O errors, rollback/readback, SCM readiness and watchdog error propagation");
}
'''
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)
    (path/'test.c').write_text(shim+source+tests)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation','-fsanitize=address,undefined','-g',str(path/'test.c'),'-o',str(path/'test')],check=True)
    subprocess.run([str(path/'test')],check=True, env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})
