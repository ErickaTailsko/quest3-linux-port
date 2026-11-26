// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/reboot.h>
#include <linux/syscore_ops.h>
#include <linux/cpu.h>
#include <linux/preempt.h>
#include <linux/interrupt.h>
#include <linux/sched.h>
#include <linux/atomic.h>
#include <linux/limits.h>

/* Passive observation only. No restart request, CPU hotplug, private symbol,
 * firmware command, MMIO access, driver callback or payload transition.
 * A normal reboot must be planned separately and logs must be recoverable.
 */
static bool observe;
module_param(observe, bool, 0);
MODULE_PARM_DESC(observe, "Register passive reboot/syscore/restart observers; default false");
static bool active;
static atomic_t sequence = ATOMIC_INIT(0);
static atomic_t restart_seen = ATOMIC_INIT(0);

static void q3_record(const char *phase)
{
	/* Snapshots only. No CPU-map locks, allocation or sleeping at final stage.
	 * This neither tests CPU-off completion nor proves DMA quiescence.
	 */
	pr_emerg("q3_handoff_observer: seq=%d phase=%s pid=%d cpu=%u online=%u irq_off=%d preempt=%u\n",
		 atomic_inc_return(&sequence), phase, task_pid_nr(current),
		 raw_smp_processor_id(), num_online_cpus(),
		 !!irqs_disabled(), preempt_count());
}

static int q3_reboot_notice(struct notifier_block *nb, unsigned long action,
			    void *data)
{
	if (action == SYS_RESTART) {
		atomic_set(&restart_seen, 1);
		q3_record("reboot-notifier");
	}
	return NOTIFY_DONE;
}

static void q3_syscore_shutdown(void)
{
	if (atomic_read(&restart_seen))
		q3_record("syscore-shutdown");
}

static int q3_restart_notice(struct notifier_block *nb, unsigned long action,
			     void *data)
{
	/* Runs in the atomic restart chain. Never stop or replace that chain. */
	if (atomic_read(&restart_seen))
		q3_record("restart-handler");
	return NOTIFY_DONE;
}

static struct notifier_block q3_reboot = {
	.notifier_call = q3_reboot_notice,
};
static struct syscore_ops q3_syscore = {
	.shutdown = q3_syscore_shutdown,
};
static struct notifier_block q3_restart = {
	.notifier_call = q3_restart_notice,
	/* Observe before lower priority handlers if reached; no precedence claim
	 * over all installed handlers, especially equal-priority earlier ones.
	 */
	.priority = INT_MAX,
};

static int __init q3_observer_init(void)
{
	int ret;

	if (!observe) {
		pr_info("q3_handoff_observer: disabled; no callbacks registered\n");
		return 0;
	}
	ret = register_restart_handler(&q3_restart);
	if (ret)
		return ret;
	register_syscore_ops(&q3_syscore);
	ret = register_reboot_notifier(&q3_reboot);
	if (ret) {
		unregister_syscore_ops(&q3_syscore);
		unregister_restart_handler(&q3_restart);
		return ret;
	}
	active = true;
	pr_info("q3_handoff_observer: passive callbacks registered; no reboot requested\n");
	return 0;
}

static void __exit q3_observer_exit(void)
{
	if (!active)
		return;
	unregister_reboot_notifier(&q3_reboot);
	unregister_syscore_ops(&q3_syscore);
	unregister_restart_handler(&q3_restart);
	active = false;
}
module_init(q3_observer_init);
module_exit(q3_observer_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Passive Quest 3 CFI-compatible shutdown phase observer");
