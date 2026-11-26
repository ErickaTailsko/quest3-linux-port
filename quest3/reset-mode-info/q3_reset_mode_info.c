// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/reboot.h>

/* Snapshots of exported globals only. No notifier, reset, firmware call,
 * private symbol resolution or writes to reboot_mode/panic_reboot_mode.
 */
static int observed_mode;
static int observed_panic_mode;
module_param(observed_mode, int, 0444);
module_param(observed_panic_mode, int, 0444);
MODULE_PARM_DESC(observed_mode, "Read-only snapshot: -1 undefined, 0 cold, 1 warm, 2 hard, 3 soft, 4 gpio");
MODULE_PARM_DESC(observed_panic_mode, "Read-only snapshot of panic_reboot_mode");

static int __init q3_reset_info_init(void)
{
	observed_mode = READ_ONCE(reboot_mode);
	observed_panic_mode = READ_ONCE(panic_reboot_mode);
	pr_info("q3_reset_mode_info: current=%d panic=%d; exported data read only, no reset or mode change\n",
		observed_mode, observed_panic_mode);
	return 0;
}
static void __exit q3_reset_info_exit(void) { }
module_init(q3_reset_info_init);
module_exit(q3_reset_info_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only snapshot of exported Quest 3 reset-mode globals");
