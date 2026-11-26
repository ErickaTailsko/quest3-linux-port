// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/cpu.h>
#include <linux/sched.h>
#include <linux/cpumask.h>
#include <linux/errno.h>

/* Independent rehearsal only. Not a kexec shutdown implementation.
 * remove_cpu/add_cpu serialize each operation, not the whole experiment.
 * Concurrent platform hotplug remains possible and is reported as failure.
 */
static int target_cpu = -1;
module_param(target_cpu, int, 0);
MODULE_PARM_DESC(target_cpu, "-1: inspect only; positive: offline/restore one CPU (experimental)");

static int q3_cpu_cycle(unsigned int cpu)
{
 cpumask_t saved, before, expected;
 int ret, restore, affinity;
 bool owned = false;
 cpumask_copy(&saved, &current->cpus_mask);
 cpus_read_lock();
 cpumask_copy(&before, cpu_online_mask);
 cpus_read_unlock();
 if (!cpu || cpu >= nr_cpu_ids || !cpu_possible(cpu) ||
     !cpumask_test_cpu(cpu, &before) || !cpumask_test_cpu(0, &before))
  return -EINVAL;
 ret = set_cpus_allowed_ptr(current, cpumask_of(0));
 if (ret)
  return ret;
 ret = remove_cpu(cpu);
 /* device_offline returns 1 when already offline: not our transition. */
 if (ret == 0) {
  owned = true;
  cpumask_copy(&expected, &before);
  cpumask_clear_cpu(cpu, &expected);
  cpus_read_lock();
  if (!cpumask_equal(&expected, cpu_online_mask))
   ret = -EAGAIN;
  cpus_read_unlock();
 } else if (ret > 0) {
  ret = -EAGAIN;
 }
 /* Never jump, wait offline, or touch another CPU. Always attempt restore
  * after a successful removal, including when validation failed.
  */
 if (owned) {
  restore = add_cpu(cpu);
  pr_info("q3_cpu_probe: cpu%u restore=%d\n", cpu, restore);
  if (restore < 0 && !ret)
   ret = restore;
 }
 cpus_read_lock();
 if (!cpumask_equal(&before, cpu_online_mask) && !ret)
  ret = -EIO;
 cpus_read_unlock();
 affinity = set_cpus_allowed_ptr(current, &saved);
 pr_info("q3_cpu_probe: cpu%u affinity_restore=%d result=%d\n", cpu, affinity, ret);
 return ret ? ret : affinity;
}
static int __init q3_cpu_probe_init(void)
{
 if (target_cpu == -1) {
  cpus_read_lock();
  pr_info("q3_cpu_probe: inspection only; online=%u possible=%u; no hotplug performed\n",
          num_online_cpus(), num_possible_cpus());
  cpus_read_unlock();
  return 0;
 }
 if (target_cpu <= 0)
  return -EINVAL;
 return q3_cpu_cycle(target_cpu);
}
static void __exit q3_cpu_probe_exit(void) {}
module_init(q3_cpu_probe_init);
module_exit(q3_cpu_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Quest 3 exported-API CPU hotplug rehearsal; not kexec");
