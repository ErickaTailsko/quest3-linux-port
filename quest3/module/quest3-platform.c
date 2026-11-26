// SPDX-License-Identifier: GPL-2.0
#include <linux/err.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/qcom_scm.h>
#include <linux/sched/clock.h>
#include "core.h"
#include "quest3-platform.h"

int qkx_restore_error(int primary, int cleanup, const char *operation)
{
	if (cleanup)
		pr_err("quest_kexec: %s restoration failed: %d (primary=%d)\n",
		       operation, cleanup, primary);
	return primary ? primary : cleanup;
}

/* Call only with the controller device locked; a module reference alone does
 * not prevent driver unbind. Never dereference saved drvdata after unbind.
 */
static bool qkx_usb_valid(struct qkx_usb *usb)
{
	struct dwc3 *dwc;

	if (usb->dev->driver != usb->driver)
		return false;
	dwc = dev_get_drvdata(usb->dev);
	return dwc && dwc->dev == usb->dev && dwc->gadget == usb->gadget;
}

int qkx_usb_get(struct qkx_usb *usb, struct device *dev)
{
	struct dwc3 *dwc;
	int ret = -ENODEV;

	if (!dev)
		return -ENODEV;
	device_lock(dev);
	if (!dev->driver || strcmp(dev->driver->name, "dwc3"))
		goto out;
	dwc = dev_get_drvdata(dev);
	if (!dwc || dwc->dev != dev || !dwc->gadget ||
	    !dwc->gadget->ops || !dwc->gadget->ops->pullup)
		goto out;
	if (!try_module_get(dev->driver->owner))
		goto out;
	usb->owner = dev->driver->owner;
	usb->driver = dev->driver;
	usb->dev = get_device(dev);
	usb->gadget = dwc->gadget;
	get_device(&usb->gadget->dev);
	ret = 0;
out:
	device_unlock(dev);
	return ret;
}

int qkx_usb_disconnect(struct qkx_usb *usb)
{
	int ret = -ENODEV;

	if (!usb->dev)
		return ret;
	device_lock(usb->dev);
	if (!qkx_usb_valid(usb))
		goto out;
	ret = -EBUSY;
	if (usb->attempted)
		goto out;
	usb->was_connected = usb->gadget->connected;
	/* DWC3 sets softconnect before runtime-PM/RunStop can fail. Attempt
	 * restoration even on failure, and leave an originally disconnected
	 * gadget disconnected. Its pullup handles runtime-suspended hardware.
	 */
	usb->attempted = usb->was_connected;
	ret = usb_gadget_disconnect(usb->gadget);
out:
	device_unlock(usb->dev);
	return ret;
}

int qkx_usb_put(struct qkx_usb *usb, bool rollback)
{
	int ret = 0;

	if (!usb->dev)
		return 0;
	if (rollback && usb->attempted) {
		device_lock(usb->dev);
		ret = qkx_usb_valid(usb) ? usb_gadget_connect(usb->gadget) : -ENODEV;
		device_unlock(usb->dev);
	}
	put_device(&usb->gadget->dev);
	put_device(usb->dev);
	module_put(usb->owner);
	memset(usb, 0, sizeof(*usb));
	return ret;
}

static bool qkx_watchdog_valid(struct qkx_watchdog *wdt)
{
	return wdt->dev->driver == wdt->driver &&
		dev_get_drvdata(wdt->dev) == wdt->data;
}

int qkx_watchdog_get(struct qkx_watchdog *wdt, struct device *dev,
		     bool retain, bool timing)
{
	struct msm_watchdog_data *data;
	int ret = -ENODEV;

	/* No get-bite-time operation exists: do not guess a rollback value. */
	if (timing)
		return -EOPNOTSUPP;
	if (!dev)
		return ret;
	device_lock(dev);
	if (!dev->driver || strcmp(dev->driver->name, "gh-watchdog") ||
	    (!of_device_is_compatible(dev->of_node, "qcom,gh-watchdog") &&
	     !of_device_is_compatible(dev->of_node, "qcom,hh-watchdog")))
		goto out;
	data = dev_get_drvdata(dev);
	if (!data || data->dev != dev || !data->ops ||
	    !data->ops->reset_wdt || !data->ops->disable_wdt ||
	    !data->ops->enable_wdt || IS_ERR_OR_NULL(data->watchdog_task))
		goto out;
	/* A disabled/panic-only driver may not have initialized its timers. */
	ret = -EOPNOTSUPP;
	if (!data->enabled)
		goto out;
	if (!try_module_get(dev->driver->owner))
		goto out;
	wdt->dev = get_device(dev);
	wdt->driver = dev->driver;
	wdt->data = data;
	wdt->owner = dev->driver->owner;
	wdt->retained = retain;
	ret = 0;
out:
	device_unlock(dev);
	return ret;
}

/* device_lock and disable_lock must be held. Unlike the exported PM helpers,
 * every hardware callback here has its return value checked.
 */
static int qkx_watchdog_restore(struct qkx_watchdog *wdt)
{
	struct msm_watchdog_data *data = wdt->data;
	unsigned long flags;
	int ret = 0, err;

	if (!wdt->suspended)
		return 0;
	if (wdt->disable_attempted) {
		/* Force the callback to contact the hypervisor even if disable
		 * failed after a partial change. An ambiguous result is an error,
		 * not proof that the original hardware state was restored.
		 */
		WRITE_ONCE(data->enabled, false);
		ret = data->ops->enable_wdt(3, data);
		WRITE_ONCE(data->enabled, true);
		if (ret)
			pr_err("quest_kexec: watchdog enable failed; hardware state uncertain: %d\n", ret);
	}
	err = data->ops->reset_wdt(data);
	ret = qkx_restore_error(ret, err, "watchdog reset");
	if (!err)
		data->last_pet = sched_clock();
	/* Resume pet scheduling even if the hypervisor rejected restoration. */
	spin_lock_irqsave(&data->freeze_lock, flags);
	data->freeze_in_progress = false;
	if (wdt->pet_pending)
		mod_timer(&data->pet_timer, jiffies + msecs_to_jiffies(data->pet_time));
	spin_unlock_irqrestore(&data->freeze_lock, flags);
	if (wdt->user_pending)
		mod_timer(&data->user_pet_timer,
			  jiffies + msecs_to_jiffies(data->bark_time + 3000));
	wdt->suspended = false;
	return ret;
}

int qkx_watchdog_prepare(struct qkx_watchdog *wdt)
{
	struct msm_watchdog_data *data = wdt->data;
	unsigned long flags;
	int ret = -ENODEV;

	if (!wdt->dev)
		return ret;
	device_lock(wdt->dev);
	if (!qkx_watchdog_valid(wdt))
		goto out_device;
	mutex_lock(&data->disable_lock);
	ret = -EBUSY;
	if (!data->enabled || data->in_panic || wdt->suspended)
		goto out;
	spin_lock_irqsave(&data->freeze_lock, flags);
	if (data->freeze_in_progress) {
		spin_unlock_irqrestore(&data->freeze_lock, flags);
		goto out;
	}
	data->freeze_in_progress = true;
	spin_unlock_irqrestore(&data->freeze_lock, flags);
	wdt->suspended = true;
	/* del_timer_sync also waits for callbacks already running. Always
	 * restart the pet timer: the pet thread may have consumed the previous
	 * expiration while freeze_in_progress prevented it from rearming.
	 */
	wdt->pet_pending = true;
	del_timer_sync(&data->pet_timer);
	wdt->user_pending = data->user_pet_enabled;
	if (wdt->user_pending)
		del_timer_sync(&data->user_pet_timer);
	ret = data->ops->reset_wdt(data);
	if (ret)
		goto out;
	data->last_pet = sched_clock();
	if (!wdt->retained) {
		wdt->disable_attempted = true;
		ret = data->ops->disable_wdt(data);
		if (!ret)
			WRITE_ONCE(data->enabled, false);
	}
out:
	mutex_unlock(&data->disable_lock);
out_device:
	device_unlock(wdt->dev);
	/* Caller performs reverse-order rollback, including partial failures. */
	return ret;
}

int qkx_watchdog_finish(struct qkx_watchdog *wdt, bool recovery)
{
	struct msm_watchdog_data *data = wdt->data;
	int ret = -ENODEV;

	if (!wdt->dev)
		return ret;
	device_lock(wdt->dev);
	if (!qkx_watchdog_valid(wdt))
		goto out_device;
	mutex_lock(&data->disable_lock);
	ret = -EINVAL;
	if (!wdt->suspended)
		goto out;
	ret = 0;
	if (!wdt->retained)
		goto out;
	if (recovery) {
		ret = data->ops->reset_wdt(data);
		if (!ret)
			data->last_pet = sched_clock();
	} else {
		wdt->disable_attempted = true;
		ret = data->ops->disable_wdt(data);
		if (!ret)
			WRITE_ONCE(data->enabled, false);
	}
out:
	mutex_unlock(&data->disable_lock);
out_device:
	device_unlock(wdt->dev);
	return ret;
}

int qkx_watchdog_put(struct qkx_watchdog *wdt, bool rollback)
{
	int ret = 0;

	if (!wdt->dev)
		return 0;
	if (rollback && wdt->suspended) {
		device_lock(wdt->dev);
		if (qkx_watchdog_valid(wdt)) {
			mutex_lock(&wdt->data->disable_lock);
			ret = qkx_watchdog_restore(wdt);
			mutex_unlock(&wdt->data->disable_lock);
		} else {
			ret = -ENODEV;
		}
		device_unlock(wdt->dev);
	}
	put_device(wdt->dev);
	module_put(wdt->owner);
	memset(wdt, 0, sizeof(*wdt));
	return ret;
}

int qkx_platform_abort(struct qkx_usb *usb, struct qkx_watchdog *wdt, int error)
{
	error = qkx_restore_error(error, qkx_watchdog_put(wdt, true), "watchdog");
	return qkx_restore_error(error, qkx_usb_put(usb, true), "USB");
}

/* The matching adreno driver publishes these exact callbacks in dev_pm_ops.
 * No KGSL private layout, symbol lookup or function-pointer cast is needed.
 */
static bool qkx_gpu_valid(struct qkx_gpu *gpu)
{
	return gpu->dev->driver == gpu->driver &&
		gpu->driver->pm == gpu->pm &&
		dev_get_drvdata(gpu->dev) == gpu->data;
}

int qkx_gpu_get(struct qkx_gpu *gpu, struct device *dev)
{
	int ret = -ENODEV;

	if (!dev)
		return ret;
	device_lock(dev);
	if (!dev->driver || strcmp(dev->driver->name, "kgsl-3d") ||
	    !dev_get_drvdata(dev))
		goto out;
	ret = -EOPNOTSUPP;
	if (!dev->driver->pm || !dev->driver->pm->suspend ||
	    !dev->driver->pm->resume)
		goto out;
	/* This adapter is for the matching KGSL system-sleep implementation.
	 * A driver with runtime callbacks needs separate PM coordination.
	 */
	if (dev->driver->pm->runtime_suspend || dev->driver->pm->runtime_resume)
		goto out;
	ret = -ENODEV;
	if (!try_module_get(dev->driver->owner))
		goto out;
	gpu->dev = get_device(dev);
	gpu->driver = dev->driver;
	gpu->pm = dev->driver->pm;
	gpu->owner = dev->driver->owner;
	gpu->data = dev_get_drvdata(dev);
	ret = 0;
out:
	device_unlock(dev);
	return ret;
}

/* Caller must freeze userspace and hold the system-sleep lock, as qkx_execute
 * does. The device lock protects binding/drvdata across the typed callback.
 */
int qkx_gpu_suspend(struct qkx_gpu *gpu)
{
	int ret = -ENODEV;

	if (!gpu->dev)
		return ret;
	device_lock(gpu->dev);
	if (!qkx_gpu_valid(gpu))
		goto out;
	ret = -EBUSY;
	if (gpu->attempted || gpu->dev->power.is_suspended)
		goto out;
	/* Like the previous implementation, try resume on a partial failure. */
	gpu->attempted = true;
	ret = gpu->pm->suspend(gpu->dev);
out:
	device_unlock(gpu->dev);
	return ret;
}

int qkx_gpu_put(struct qkx_gpu *gpu, bool rollback)
{
	int ret = 0;

	if (!gpu->dev)
		return 0;
	if (rollback && gpu->attempted) {
		device_lock(gpu->dev);
		ret = qkx_gpu_valid(gpu) ? gpu->pm->resume(gpu->dev) : -ENODEV;
		device_unlock(gpu->dev);
	}
	put_device(gpu->dev);
	module_put(gpu->owner);
	memset(gpu, 0, sizeof(*gpu));
	return ret;
}

/* Deliberately no disconnect, watchdog callback, timer or SCM command here.
 * This checks only the running board's bindings and required operations.
 */
int qkx_platform_preflight(void)
{
	struct device *usb_dev, *wdt_dev, *gpu_dev;
	struct qkx_usb usb = { };
	struct qkx_watchdog wdt = { };
	struct qkx_gpu gpu = { };
	int ret;

	if (!qcom_scm_is_available()) {
		pr_err("quest_kexec: preflight: SCM driver unavailable\n");
		return -ENODEV;
	}
	usb_dev = bus_find_device_by_name(&platform_bus_type, NULL, "a600000.dwc3");
	wdt_dev = bus_find_device_by_name(&platform_bus_type, NULL,
					"hypervisor:qcom,gh-watchdog");
	gpu_dev = bus_find_device_by_name(&platform_bus_type, NULL, "3d00000.qcom,kgsl-3d0");
	ret = qkx_gpu_get(&gpu, gpu_dev);
	if (ret) {
		pr_err("quest_kexec: preflight: KGSL PM operations unavailable: %d\n", ret);
		goto out;
	}
	ret = qkx_usb_get(&usb, usb_dev);
	if (ret) {
		pr_err("quest_kexec: preflight: USB binding/operations unavailable: %d\n", ret);
		goto out;
	}
	ret = qkx_watchdog_get(&wdt, wdt_dev, false, false);
	if (ret)
		pr_err("quest_kexec: preflight: active Gunyah watchdog unavailable: %d\n", ret);
	else
		pr_info("quest_kexec: read-only platform preflight passed; GPU/USB/watchdog bindings and SCM driver ready; firmware commands and kexec NOT tested\n");
out:
	ret = qkx_restore_error(ret, qkx_watchdog_put(&wdt, false), "preflight watchdog references");
	ret = qkx_restore_error(ret, qkx_usb_put(&usb, false), "preflight USB references");
	ret = qkx_restore_error(ret, qkx_gpu_put(&gpu, false), "preflight GPU references");
	put_device(gpu_dev);
	put_device(wdt_dev);
	put_device(usb_dev);
	return ret;
}
