from pathlib import Path
import subprocess,tempfile
p=Path(__file__).parent
src=(p/'q3_cpu_probe.c').read_text()
fn=src[src.index('static int q3_cpu_cycle'):src.index('static int __init')]
mock=r'''
#include <stdbool.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
typedef unsigned cpumask_t;
static unsigned online=7, zero=1;
#define cpu_online_mask (&online)
struct task { cpumask_t cpus_mask; } task={7};
#define current (&task)
#define nr_cpu_ids 3
#define cpu_possible(n) ((n)<3)
#define cpumask_copy(a,b) (*(a)=*(b))
#define cpumask_test_cpu(n,m) ((*(m))&(1u<<(n)))
#define cpumask_clear_cpu(n,m) (*(m)&=~(1u<<(n)))
#define cpumask_equal(a,b) (*(a)==*(b))
#define cpumask_of(n) (&zero)
#define cpus_read_lock() ((void)0)
#define cpus_read_unlock() ((void)0)
#define pr_info(...) ((void)0)
static int downret,upret,afffail,downcalls,upcalls,affcalls,race;
static int set_cpus_allowed_ptr(struct task*t,const unsigned*m) {
 affcalls++; if(afffail==affcalls)return -EPERM;t->cpus_mask=*m;return 0;
}
static int remove_cpu(unsigned c){downcalls++;if(downret)return downret; online &=~(1u<<c);if(race)online &=~4u;return 0;}
static int add_cpu(unsigned c){upcalls++;if(upret<0)return upret;online|=1u<<c;return upret;}
static void reset(void){online=7;task.cpus_mask=7;downret=upret=afffail=downcalls=upcalls=affcalls=race=0;}
'''
tests=r'''
int main(void){
reset();assert(q3_cpu_cycle(1)==0);assert(online==7&&task.cpus_mask==7&&upcalls==1);
reset();assert(q3_cpu_cycle(0)==-EINVAL);assert(!downcalls&&!affcalls);
reset();afffail=1;assert(q3_cpu_cycle(1)==-EPERM);assert(!downcalls);
reset();downret=-EBUSY;assert(q3_cpu_cycle(1)==-EBUSY);assert(!upcalls&&task.cpus_mask==7);
reset();downret=1;assert(q3_cpu_cycle(1)==-EAGAIN);assert(!upcalls);
reset();upret=-EIO;assert(q3_cpu_cycle(1)==-EIO);assert(upcalls==1&&task.cpus_mask==7);
reset();race=1;assert(q3_cpu_cycle(1)==-EAGAIN);assert(upcalls==1&&task.cpus_mask==7);
reset();race=1;upret=-EIO;assert(q3_cpu_cycle(1)==-EAGAIN);assert(upcalls==1);
reset();afffail=2;assert(q3_cpu_cycle(1)==-EPERM);assert(online==7);
puts("PASS: success, CPU0 refusal, affinity failures, offline failure, already offline, restore failure, concurrent mask changes, error precedence");
}
'''
with tempfile.TemporaryDirectory() as d:
 f=Path(d)/'test.c';f.write_text(mock+fn+tests)
 subprocess.run(['cc','-Wall','-Wextra','-Werror',str(f),'-o',d+'/test'],check=True)
 subprocess.run([d+'/test'],check=True)
