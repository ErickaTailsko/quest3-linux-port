// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/cpu.h>
#include <linux/sched.h>
#include <linux/cpumask.h>
#include <linux/errno.h>

/* Prototype: each API locks individually; no global hotplug exclusion.
 * Active hardware dispatch deliberately blocked pending concurrency review.
 */
static int count;
module_param(count, int, 0);
static bool q3_mask_matches(const cpumask_t *mask)
{
 bool equal;
 cpus_read_lock();
 equal = cpumask_equal(mask, cpu_online_mask);
 cpus_read_unlock();
 return equal;
}
static int __used q3_multi_cycle(int limit)
{
 cpumask_t saved, before, expected, removed;
 int cpu, available = 0, done = 0, ret = 0, err;
 cpumask_copy(&saved, &current->cpus_mask);
 cpus_read_lock();
 cpumask_copy(&before, cpu_online_mask);
 cpus_read_unlock();
 for_each_cpu(cpu, &before)
  if (cpu) available++;
 if (limit <= 0 || limit > available || !cpumask_test_cpu(0, &before))
  return -EINVAL;
 cpumask_copy(&expected, &before);
 cpumask_clear(&removed);
 ret = set_cpus_allowed_ptr(current, cpumask_of(0));
 if (ret) return ret;
 for_each_cpu(cpu, &before) {
  if (!cpu || done == limit) continue;
  if (!q3_mask_matches(&expected)) { ret = -EAGAIN; break; }
  err = remove_cpu(cpu);
  pr_info("q3_cpu_multi: remove cpu%d=%d\n", cpu, err);
  if (err) { ret = err < 0 ? err : -EAGAIN; break; }
  cpumask_set_cpu(cpu, &removed);
  cpumask_clear_cpu(cpu, &expected);
  done++;
  if (!q3_mask_matches(&expected)) { ret = -EAGAIN; break; }
 }
 /* Serialize only the final checkpoint. Never call remove_cpu/add_cpu
  * while holding cpu_add_remove_lock: both acquire it internally.
  * This is not exclusion for the entire transaction, nor against firmware.
  */
 if (!ret) {
  cpu_maps_update_begin();
  if (!q3_mask_matches(&expected))
   ret = -EAGAIN;
  else
   pr_info("q3_cpu_multi: final mask checked under CPU maps lock; no jump\n");
  cpu_maps_update_done();
 }
 /* Reverse removal order; a restore failure never skips later restores. */
 for (cpu = nr_cpu_ids - 1; cpu > 0; cpu--) {
  if (!cpumask_test_cpu(cpu, &removed)) continue;
  err = add_cpu(cpu);
  pr_info("q3_cpu_multi: restore cpu%d=%d\n", cpu, err);
  if (err < 0 && !ret) ret = err;
 }
 if (!q3_mask_matches(&before) && !ret) ret = -EIO;
 err = set_cpus_allowed_ptr(current, &saved);
 pr_info("q3_cpu_multi: affinity_restore=%d primary=%d\n", err, ret);
 return ret ? ret : err;
}
static int __init q3_multi_init(void)
{
 if (count) {
  pr_err("q3_cpu_multi: active rehearsal blocked pending hotplug concurrency review\n");
  return -EOPNOTSUPP;
 }
 cpus_read_lock();
 pr_info("q3_cpu_multi: inspection only; online=%u\n", num_online_cpus());
 cpus_read_unlock();
 return 0;
}
static void __exit q3_multi_exit(void) {}
module_init(q3_multi_init);
module_exit(q3_multi_exit);
MODULE_LICENSE("GPL");
