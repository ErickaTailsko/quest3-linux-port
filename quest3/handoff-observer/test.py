#!/usr/bin/env python3
"""Compile the production source against lifecycle/error-injection host stubs."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent
source = '\n'.join(line for line in (root / 'q3_handoff_observer.c').read_text().splitlines()
                   if not line.startswith('#include'))
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <limits.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#define __init
#define __exit
#define module_param(a,b,c)
#define MODULE_PARM_DESC(a,b)
#define module_init(a)
#define module_exit(a)
#define MODULE_LICENSE(a)
#define MODULE_DESCRIPTION(a)
#define SYS_RESTART 1
#define NOTIFY_DONE 0
#define pr_info(...) ((void)0)
typedef struct {int value;} atomic_t;
#define ATOMIC_INIT(v) {v}
static int atomic_read(atomic_t *p) {return p->value;}
static void atomic_set(atomic_t *p,int v) {p->value=v;}
static int atomic_inc_return(atomic_t *p) {return ++p->value;}
static int task_pid_nr(void *p) {(void)p;return 42;}
#define current ((void *)1)
static unsigned int raw_smp_processor_id(void) {return 0;}
static unsigned int num_online_cpus(void) {return 6;}
static int irqs_disabled(void) {return 0;}
static unsigned int preempt_count(void) {return 0;}
static char logs[8][512]; static int log_count;
static void record_log(const char *fmt,...) {
 va_list args; va_start(args,fmt);
 assert(log_count<8);vsnprintf(logs[log_count++],512,fmt,args);va_end(args);
}
#define pr_emerg record_log
struct notifier_block {
 int (*notifier_call)(struct notifier_block *,unsigned long,void *);
 int priority;
};
struct syscore_ops {void (*shutdown)(void);};
static struct notifier_block *reboot_hook,*restart_hook;
static struct syscore_ops *syscore_hook;
static int fail_at,register_calls,unregister_calls;
static int register_restart_handler(struct notifier_block *p) {
 register_calls++; if(fail_at==1)return -12;
 assert(!restart_hook);restart_hook=p;return 0;
}
static int unregister_restart_handler(struct notifier_block *p) {
 assert(p==restart_hook);restart_hook=0;unregister_calls++;return 0;
}
static void register_syscore_ops(struct syscore_ops *p) {
 assert(restart_hook&&!syscore_hook);syscore_hook=p;register_calls++;
}
static void unregister_syscore_ops(struct syscore_ops *p) {
 assert(p==syscore_hook);syscore_hook=0;unregister_calls++;
}
static int register_reboot_notifier(struct notifier_block *p) {
 assert(syscore_hook);register_calls++;if(fail_at==3)return -16;
 assert(!reboot_hook);reboot_hook=p;return 0;
}
static int unregister_reboot_notifier(struct notifier_block *p) {
 assert(p==reboot_hook);reboot_hook=0;unregister_calls++;return 0;
}
'''
main = r'''
int main(void) {
 assert(!q3_observer_init());q3_observer_exit();assert(!register_calls);
 observe=true;fail_at=1;
 assert(q3_observer_init()==-12);assert(!active&&!restart_hook&&!syscore_hook&&!reboot_hook);
 assert(unregister_calls==0);
 fail_at=3;
 assert(q3_observer_init()==-16);assert(!active&&!restart_hook&&!syscore_hook&&!reboot_hook);
 assert(unregister_calls==2);
 fail_at=0;assert(!q3_observer_init());assert(active);
 assert(restart_hook->priority==INT_MAX);
 syscore_hook->shutdown();assert(!log_count);
 assert(restart_hook->notifier_call(restart_hook,0,0)==NOTIFY_DONE);assert(!log_count);
 assert(reboot_hook->notifier_call(reboot_hook,2,0)==NOTIFY_DONE);assert(!log_count);
 assert(reboot_hook->notifier_call(reboot_hook,SYS_RESTART,0)==NOTIFY_DONE);
 syscore_hook->shutdown();
 assert(restart_hook->notifier_call(restart_hook,0,0)==NOTIFY_DONE);
 assert(log_count==3);
 assert(strstr(logs[0],"seq=1 phase=reboot-notifier"));
 assert(strstr(logs[1],"seq=2 phase=syscore-shutdown"));
 assert(strstr(logs[2],"seq=3 phase=restart-handler"));
 q3_observer_exit();assert(!active&&!restart_hook&&!syscore_hook&&!reboot_hook);
 assert(unregister_calls==5);q3_observer_exit();assert(unregister_calls==5);
 puts("PASS default disabled, registration failures unwind, unrelated events ignored, typed callbacks log and continue, unload unregisters all hooks");
}
'''
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / 'test.c'; binary = Path(temp) / 'test'
    path.write_text(prefix + source + main)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-fsanitize=undefined', str(path), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
