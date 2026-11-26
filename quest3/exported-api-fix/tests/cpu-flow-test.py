#!/usr/bin/env python3
from pathlib import Path
import os, subprocess, tempfile
r=Path(__file__).resolve().parents[1]
s=(r/'module/loader.c').read_text();a=s.index('static int qkx_test_cpus(void)');b=s.index('\nstatic int qkx_test_full_copy',a)
function=s[a:b]
p=(r/'module/quest3-platform.c').read_text();a=p.index('int qkx_restore_error');b=p.index('\n/*',a)
merge=p[a:b]
shim=r'''
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
typedef struct { unsigned int bits; } cpumask_t;
static cpumask_t online_mask, masks[4];
#define cpu_online_mask (&online_mask)
static struct { cpumask_t cpus_mask; } task;
#define current (&task)
#define pr_info(...) do {} while(0)
#define pr_err(...) do { errors++; } while(0)
static unsigned int test_cpus,preflight_only;
static int errors,down_fail,up_fail,freeze_error,transition_error,affinity_fail;
static int restores,affinities,downs,ups,transitions;
static void cpumask_copy(cpumask_t *d,const cpumask_t *s) { *d=*s; }
static void cpumask_clear(cpumask_t *m) { m->bits=0; }
static void cpumask_set_cpu(int c,cpumask_t *m) { m->bits|=1U<<c; }
static bool cpumask_equal(const cpumask_t *a,const cpumask_t *b) { return a->bits==b->bits; }
static bool cpu_online(int c) { return online_mask.bits&(1U<<c); }
static int num_online_cpus(void) { return __builtin_popcount(online_mask.bits); }
static const cpumask_t *cpumask_of(int c) { return &masks[c]; }
#define for_each_cpu(c,m) for((c)=0;(c)<4;(c)++) if((m)->bits&(1U<<(c)))
static int set_cpus_allowed_ptr(void *p,const cpumask_t *m) {
 assert(p==current); affinities++; if(affinities==affinity_fail) return -EACCES;
 task.cpus_mask=*m; return 0;
}
static int down(int c) { downs++; if(c==down_fail) return -ETIMEDOUT; online_mask.bits&=~(1U<<c); return 0; }
static int up(int c) { ups++; if(c==up_fail) return -EIO; online_mask.bits|=1U<<c; return 0; }
static int freeze(int c) { assert(c==0); online_mask.bits=1; return freeze_error; }
static void restore(void) { restores++; online_mask.bits=7; }
static unsigned long lookup(const char *s) {
 if(!strcmp(s,"freeze_secondary_cpus")) return (unsigned long)freeze;
 if(!strcmp(s,"enable_nonboot_cpus")) return (unsigned long)restore;
 if(!strcmp(s,"cpu_down")) return (unsigned long)down;
 if(!strcmp(s,"cpu_up")) return (unsigned long)up;
 assert(0); return 0;
}
static int qkx_test_transition(void) { transitions++; return transition_error; }
'''
tests=r'''
static void reset(void) {
 test_cpus=2;preflight_only=0;online_mask.bits=7;task.cpus_mask.bits=6;
 for(int i=0;i<4;i++) masks[i].bits=1U<<i;
 errors=freeze_error=transition_error=restores=affinities=downs=ups=transitions=0;
 down_fail=up_fail=affinity_fail=-1;
}
int main(void) {
 reset(); assert(!qkx_test_cpus() && online_mask.bits==7 && task.cpus_mask.bits==6 && downs==2 && ups==2);
 reset(); online_mask.bits=1; assert(!qkx_test_cpus() && !downs && !ups && affinities==2);
 reset(); down_fail=2; up_fail=1;
 assert(qkx_test_cpus()==-ETIMEDOUT && ups==1 && errors==2 && task.cpus_mask.bits==6);
 reset(); up_fail=1; assert(qkx_test_cpus()==-EIO && task.cpus_mask.bits==6);
 reset(); affinity_fail=1; assert(qkx_test_cpus()==-EACCES && !downs && !ups);
 reset(); affinity_fail=2; assert(qkx_test_cpus()==-EACCES && online_mask.bits==7 && errors==1);
 reset(); down_fail=2; affinity_fail=2; assert(qkx_test_cpus()==-ETIMEDOUT && errors==1);
 reset(); test_cpus=1; freeze_error=-EBUSY;
 assert(qkx_test_cpus()==-EBUSY && restores==1 && online_mask.bits==7 && task.cpus_mask.bits==6);
 reset(); test_cpus=1; preflight_only=3; transition_error=-EFAULT;
 assert(qkx_test_cpus()==-EFAULT && transitions==1 && restores==1 && task.cpus_mask.bits==6);
 reset(); online_mask.bits=6; assert(qkx_test_cpus()==-ENODEV && !affinities);
 puts("PASS: CPU0-only result, CPU restore/affinity errors, first-error retention, failed freeze cleanup and rehearsal cleanup");
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'test.c').write_text(shim+merge+function+tests)
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
