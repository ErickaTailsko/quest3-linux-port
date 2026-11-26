from pathlib import Path
import subprocess,tempfile
p=Path(__file__).parent
s=(p/'q3_cpu_multi.c').read_text()
fn=s[s.index('static bool q3_mask_matches'):s.index('static int __init')]
mock=r'''
#include <stdbool.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
#define __used
#define pr_info(...) ((void)0)
typedef unsigned cpumask_t;
static unsigned online=63, zero=1;
#define cpu_online_mask (&online)
struct task {unsigned cpus_mask;} task={63};
#define current (&task)
#define nr_cpu_ids 6
#define for_each_cpu(c,m) for(c=0;c<6;c++) if((*(m))&(1u<<c))
#define cpumask_copy(a,b) (*(a)=*(b))
#define cpumask_clear(m) (*(m)=0)
#define cpumask_set_cpu(c,m) (*(m)|=1u<<(c))
#define cpumask_clear_cpu(c,m) (*(m)&=~(1u<<(c)))
#define cpumask_test_cpu(c,m) (*(m)&(1u<<(c)))
#define cpumask_equal(a,b) (*(a)==*(b))
#define cpumask_of(c) (&zero)
#define cpus_read_lock() ((void)0)
#define cpus_read_unlock() ((void)0)
static int downcalls,upcalls,affcalls,faildown,failup,failaff,positive,race;
static int order[6], maps_locked, checkpoints, checkpoint_race;
static void cpu_maps_update_begin(void){assert(!maps_locked);maps_locked=1;checkpoints++;if(checkpoint_race)online|=2u;}
static void cpu_maps_update_done(void){assert(maps_locked);maps_locked=0;}
static int set_cpus_allowed_ptr(struct task*t,const unsigned*m){affcalls++;if(affcalls==failaff)return -EPERM;t->cpus_mask=*m;return 0;}
static int remove_cpu(unsigned c){assert(!maps_locked);downcalls++;assert(c);if(downcalls==faildown)return positive?1:-EBUSY;online&=~(1u<<c);if(race)online&=~32u;return 0;}
static int add_cpu(unsigned c){assert(!maps_locked);assert(c);order[upcalls++]=c;if((int)c==failup)return -EIO;online|=1u<<c;return 0;}
static void reset(void){assert(!maps_locked);checkpoints=checkpoint_race=0;online=task.cpus_mask=63;downcalls=upcalls=affcalls=faildown=failup=failaff=positive=race=0;}
'''
tests=r'''
int main(void){
for(int n=1;n<=5;n++){reset();assert(q3_multi_cycle(n)==0);assert(online==63&&task.cpus_mask==63&&upcalls==n);for(int i=0;i<n;i++)assert(order[i]==n-i);}
for(int f=1;f<=5;f++){reset();faildown=f;assert(q3_multi_cycle(5)==-EBUSY);assert(upcalls==f-1&&online==63&&task.cpus_mask==63);}
for(int f=1;f<=5;f++){reset();failup=f;assert(q3_multi_cycle(5)==-EIO);assert(upcalls==5&&task.cpus_mask==63);assert(online==(63u&~(1u<<f)));}
reset();faildown=3;failup=1;assert(q3_multi_cycle(5)==-EBUSY);assert(upcalls==2);
reset();faildown=2;positive=1;assert(q3_multi_cycle(5)==-EAGAIN);assert(upcalls==1);
reset();race=1;assert(q3_multi_cycle(5)==-EAGAIN);assert(downcalls==1&&upcalls==1);
reset();failaff=1;assert(q3_multi_cycle(5)==-EPERM);assert(!downcalls);
reset();failaff=2;assert(q3_multi_cycle(5)==-EPERM);assert(online==63);
reset();assert(q3_multi_cycle(0)==-EINVAL);assert(q3_multi_cycle(6)==-EINVAL);assert(!downcalls);
reset();online=62;assert(q3_multi_cycle(1)==-EINVAL);assert(!downcalls);
reset();checkpoint_race=1;assert(q3_multi_cycle(5)==-EAGAIN);assert(checkpoints==1&&!maps_locked&&online==63&&upcalls==5);
reset();assert(q3_multi_cycle(5)==0);assert(checkpoints==1&&!maps_locked);
puts("PASS: 24 scenarios; reverse restore, every removal/restore failure, primary error precedence, mask race, affinity, invalid limits and CPU0 absent");
}
'''
with tempfile.TemporaryDirectory() as d:
 f=Path(d)/'test.c'; f.write_text(mock+fn+tests)
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(f),'-o',d+'/test'],check=True)
 subprocess.run([d+'/test'],check=True)
