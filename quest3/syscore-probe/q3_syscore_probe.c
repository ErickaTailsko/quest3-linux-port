// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/syscore_ops.h>
#include <linux/cpu.h>
#include <linux/preempt.h>
#include <linux/interrupt.h>
#include <linux/sched.h>
#include <linux/efi.h>

/* Passive observer only. Never calls restart, CPU hotplug, SCM or MMIO.
 * observe=false registers nothing. observe=true observes a later shutdown
 * initiated elsewhere, then returns normally to the existing sequence.
 */
static bool observe;
module_param(observe, bool, 0);
MODULE_PARM_DESC(observe, "Register passive syscore shutdown observer; default false");
static bool registered;
static void q3_syscore_shutdown(void)
{
 pr_emerg("q3_syscore_probe: shutdown callback; pid=%d cpu=%u online=%u irq_off=%d preempt=%u efi_runtime=%d\n",
  task_pid_nr(current), raw_smp_processor_id(), num_online_cpus(),
  !!irqs_disabled(), preempt_count(), !!efi_enabled(EFI_RUNTIME_SERVICES));
 pr_emerg("q3_syscore_probe: observation only; returning without hotplug or reboot changes\n");
}
static struct syscore_ops q3_ops = { .shutdown = q3_syscore_shutdown };
static int __init q3_syscore_init(void)
{
 if (observe) {
  register_syscore_ops(&q3_ops);
  registered = true;
 }
 pr_info("q3_syscore_probe: passive observer registered=%d; no reboot requested\n", registered);
 return 0;
}
static void __exit q3_syscore_exit(void)
{
 if (registered)
  unregister_syscore_ops(&q3_ops);
}
module_init(q3_syscore_init);
module_exit(q3_syscore_exit);
MODULE_LICENSE("GPL");
