from pathlib import Path
import subprocess,tempfile,re
p=Path(__file__).parent
s=(p/'q3_syscore_probe.c').read_text()
s='\n'.join(l for l in s.splitlines() if not l.startswith('#include'))
prefix=r'''
#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
#define __init
#define __exit
#define module_param(a,b,c)
#define MODULE_PARM_DESC(a,b)
#define module_init(a)
#define module_exit(a)
#define MODULE_LICENSE(a)
#define pr_info(...) ((void)0)
#define pr_emerg(...) ((void)0)
struct syscore_ops {void (*shutdown)(void);};
static struct syscore_ops *active;
static int registrations,unregistrations;
static void register_syscore_ops(struct syscore_ops *p){assert(!active);active=p;registrations++;}
static void unregister_syscore_ops(struct syscore_ops *p){assert(active==p);active=0;unregistrations++;}
'''
main=r'''
int main(void){
assert(q3_syscore_init()==0);assert(!active&&!registrations);q3_syscore_exit();assert(!unregistrations);
observe=true;assert(q3_syscore_init()==0);assert(active&&registrations==1);
active->shutdown();assert(active&&unregistrations==0);
q3_syscore_exit();assert(!active&&unregistrations==1);
puts("PASS: default no registration; opt-in registration; observer returns; unload unregisters");
}
'''
with tempfile.TemporaryDirectory() as d:
 f=Path(d)/'test.c'; f.write_text(prefix+s+main)
 subprocess.run(['cc','-Wall','-Wextra','-Werror',str(f),'-o',d+'/test'],check=True)
 subprocess.run([d+'/test'],check=True)
