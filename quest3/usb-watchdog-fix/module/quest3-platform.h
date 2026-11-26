/* SPDX-License-Identifier: GPL-2.0 */
#ifndef QKX_QUEST3_PLATFORM_H
#define QKX_QUEST3_PLATFORM_H
#include <linux/device.h>
#include <linux/module.h>
#include <linux/usb/gadget.h>
#include <soc/qcom/watchdog.h>
struct qkx_usb {
	struct device *dev;
	struct device_driver *driver;
	struct usb_gadget *gadget;
	struct module *owner;
	bool was_connected;
	bool attempted;
};
struct qkx_watchdog {
	struct device *dev;
	struct device_driver *driver;
	struct msm_watchdog_data *data;
	struct module *owner;
	bool retained;
	bool suspended;
	bool disable_attempted;
	bool pet_pending;
	bool user_pending;
};
int qkx_usb_get(struct qkx_usb *usb, struct device *dev);
int qkx_usb_disconnect(struct qkx_usb *usb);
int qkx_usb_put(struct qkx_usb *usb, bool rollback);
int qkx_watchdog_get(struct qkx_watchdog *wdt, struct device *dev,
		     bool retain, bool timing);
int qkx_watchdog_prepare(struct qkx_watchdog *wdt);
int qkx_watchdog_finish(struct qkx_watchdog *wdt, bool recovery);
int qkx_watchdog_put(struct qkx_watchdog *wdt, bool rollback);
int qkx_restore_error(int primary, int cleanup, const char *operation);
int qkx_platform_abort(struct qkx_usb *usb, struct qkx_watchdog *wdt, int error);
#endif
