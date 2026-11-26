// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/efi.h>
static int __init q3_restart_info_init(void)
{
 pr_info("q3_restart_info: read-only EFI_BOOT=%d EFI_RUNTIME_SERVICES=%d RESET_SYSTEM_SUPPORTED=%d\n",
  !!efi_enabled(EFI_BOOT), !!efi_enabled(EFI_RUNTIME_SERVICES),
  !!efi_rt_services_supported(EFI_RT_SUPPORTED_RESET_SYSTEM));
 pr_info("q3_restart_info: no restart handlers registered; no reboot or firmware command issued\n");
 return 0;
}
static void __exit q3_restart_info_exit(void) {}
module_init(q3_restart_info_init);
module_exit(q3_restart_info_exit);
MODULE_LICENSE("GPL");
