// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/reboot.h>
#include <linux/errno.h>
#include <linux/atomic.h>
#include "q3_warm_state.h"

/* No firmware call, reboot request or notifier is made by this module.
 * Default arm=false only reads state. arm=true opts into the exported global
 * policy change until unload or kernel reset; firmware behavior is untested.
 */
static bool arm;
module_param(arm, bool, 0444);
MODULE_PARM_DESC(arm, "Default false: inspect only; true: override COLD with WARM until unload/reset");
static struct q3_warm_state state;
static int prior_snapshot;
module_param(prior_snapshot, int, 0444);
MODULE_PARM_DESC(prior_snapshot, "Observed reset mode before optional override");

static int q3_current_mode_get(char *buffer, const struct kernel_param *parameter)
{
	return scnprintf(buffer, 32, "%d\n", READ_ONCE(reboot_mode));
}
static const struct kernel_param_ops q3_current_ops = { .get = q3_current_mode_get };
module_param_cb(current_mode, &q3_current_ops, NULL, 0444);
MODULE_PARM_DESC(current_mode, "Live read-only exported reboot_mode value");

static int q3_owned_get(char *buffer, const struct kernel_param *parameter)
{
	return scnprintf(buffer, 32, "%u\n", READ_ONCE(state.owned));
}
static const struct kernel_param_ops q3_owned_ops = { .get = q3_owned_get };
module_param_cb(override_owned, &q3_owned_ops, NULL, 0444);

static int __init q3_guard_init(void)
{
	int ret;

	prior_snapshot = READ_ONCE(reboot_mode);
	if (!arm) {
		pr_info("q3_warm_reset_guard: inspect only, current=%d; no mode change or reboot\n",
			prior_snapshot);
		return 0;
	}
	ret = q3_warm_acquire(&state);
	if (ret)
		return ret;
	/* No fallible setup after the policy mutation. This does not imply the
	 * requested warm path exists or will preserve RAM. Panic fallback can
	 * also inherit this policy when panic_reboot_mode is UNDEFINED.
	 */
	pr_warn("q3_warm_reset_guard: COLD overridden with WARM; panic_mode=%d unchanged; no reboot requested; unload to restore if policy still matches\n",
		READ_ONCE(panic_reboot_mode));
	return 0;
}

static void __exit q3_guard_exit(void)
{
	if (state.owned && !q3_warm_release(&state))
		pr_warn("q3_warm_reset_guard: reset policy changed by another actor; not overwritten\n");
}
module_init(q3_guard_init);
module_exit(q3_guard_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Opt-in COLD-to-WARM policy override; default read-only, no reboot call");
