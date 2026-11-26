#!/usr/bin/env python3
"""Run production USB/watchdog state handling against fault-injected APIs."""
from pathlib import Path
import os, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
def stripped(p):
    return '\n'.join(x for x in p.read_text().splitlines() if not x.startswith('#include'))
shim = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
struct module { int refs; } owner;
struct device_driver { const char *name; struct module *owner; } usb_driver, wdt_driver;
struct device { struct device_driver *driver; void *data; const char *of_node; int refs, locked; } usbdev, wdtdev;
struct usb_gadget;
struct usb_gadget_ops { int (*pullup)(struct usb_gadget *, int); } gadget_ops;
struct usb_gadget { struct device dev; struct usb_gadget_ops *ops; bool connected; } gadget;
struct dwc3 { struct device *dev; struct usb_gadget *gadget; } dwc;
struct mutex { int held; };
struct timer_list { bool pending; unsigned long expires; };
struct msm_watchdog_data;
struct qcom_wdt_ops {
 int (*reset_wdt)(struct msm_watchdog_data *);
 int (*disable_wdt)(struct msm_watchdog_data *);
 int (*enable_wdt)(u32, struct msm_watchdog_data *);
} ops;
struct msm_watchdog_data {
 struct device *dev; struct qcom_wdt_ops *ops; void *watchdog_task;
 bool enabled, in_panic, freeze_in_progress, user_pet_enabled;
 struct mutex disable_lock; int freeze_lock;
 struct timer_list pet_timer, user_pet_timer;
 unsigned int pet_time, bark_time;
 unsigned long long last_pet;
} data;
static int log_errors, resets, disables, enables, connects, disconnects, reset_failure;
static int disable_error, enable_error, connect_error, disconnect_error;
static bool pin_ok, hw_enabled, hw_connected;
static char events[256]; static int event_count;
static void event(char c) { events[event_count++]=c; events[event_count]=0; }
#define pr_info(...) do {} while(0)
#define pr_err(...) do { log_errors++; } while(0)
#define IS_ERR_OR_NULL(x) (!(x))
#define WRITE_ONCE(x,v) ((x)=(v))
#define spin_lock_irqsave(l,f) do { (f)=0; assert(!*(l)); *(l)=1; } while(0)
#define spin_unlock_irqrestore(l,f) do { (void)(f); assert(*(l)); *(l)=0; } while(0)
static unsigned long jiffies=100;
static unsigned long msecs_to_jiffies(unsigned long x) { return x; }
static unsigned long long sched_clock(void) { return 1000; }
static void mutex_lock(struct mutex *m) { assert(!m->held); m->held=1; }
static void mutex_unlock(struct mutex *m) { assert(m->held); m->held=0; }
static void device_lock(struct device *d) { assert(!d->locked); d->locked=1; }
static void device_unlock(struct device *d) { assert(d->locked); d->locked=0; }
static struct device *get_device(struct device *d) { d->refs++; return d; }
static void put_device(struct device *d) { if(d) { d->refs--; assert(d->refs>=0); } }
static void *dev_get_drvdata(struct device *d) { return d->data; }
static bool try_module_get(struct module *m) { if(!pin_ok) return false; m->refs++; return true; }
static void module_put(struct module *m) { m->refs--; assert(m->refs>=0); }
static bool of_device_is_compatible(const char *n,const char *s) { return n && !strcmp(n,s); }
static int del_timer_sync(struct timer_list *t) { int p=t->pending; t->pending=false; return p; }
static int mod_timer(struct timer_list *t,unsigned long e) { t->pending=true; t->expires=e; return 0; }
static int pullup(struct usb_gadget *g,int on) { return 0; }
static int platform_bus_type;
static bool scm_ready=true, missing_usb, missing_wdt;
static bool qcom_scm_is_available(void) { return scm_ready; }
static struct device *bus_find_device_by_name(int *bus, void *start, const char *name) {
 assert(bus==&platform_bus_type && !start);
 if(!strcmp(name,"a600000.dwc3")) return missing_usb?NULL:get_device(&usbdev);
 assert(!strcmp(name,"hypervisor:qcom,gh-watchdog"));
 return missing_wdt?NULL:get_device(&wdtdev);
}
static int usb_gadget_connect(struct usb_gadget *g) {
 event('C'); connects++; hw_connected=true;
 if(connect_error) return connect_error; g->connected=true; return 0;
}
static int usb_gadget_disconnect(struct usb_gadget *g) {
 if(!g->connected) return 0;
 event('D'); disconnects++; hw_connected=false;
 if(disconnect_error) return disconnect_error; g->connected=false; return 0;
}
static int reset_wdt(struct msm_watchdog_data *d) {
 assert(d->disable_lock.held && d->dev->locked); event('R'); resets++;
 return resets==reset_failure ? -ETIMEDOUT : 0;
}
static int disable_wdt(struct msm_watchdog_data *d) {
 assert(d->disable_lock.held && d->dev->locked); event('X'); disables++;
 assert(d->enabled); hw_enabled=false; return disable_error;
}
static int enable_wdt(u32 val,struct msm_watchdog_data *d) {
 assert(d->disable_lock.held && d->dev->locked); event('E'); enables++;
 assert(val==3 && !d->enabled); hw_enabled=true; return enable_error;
}
'''
tests = r'''
static void reset(void) {
 memset(&owner,0,sizeof(owner)); memset(&usbdev,0,sizeof(usbdev)); memset(&wdtdev,0,sizeof(wdtdev));
 memset(&gadget,0,sizeof(gadget)); memset(&data,0,sizeof(data));
 usb_driver=(struct device_driver){"dwc3",&owner}; wdt_driver=(struct device_driver){"gh-watchdog",&owner};
 usbdev.driver=&usb_driver; usbdev.data=&dwc; wdtdev.driver=&wdt_driver; wdtdev.data=&data;
 wdtdev.of_node="qcom,gh-watchdog"; dwc=(struct dwc3){&usbdev,&gadget};
 gadget_ops.pullup=pullup; gadget.ops=&gadget_ops; gadget.connected=true;
 ops=(struct qcom_wdt_ops){reset_wdt,disable_wdt,enable_wdt};
 data.dev=&wdtdev; data.ops=&ops; data.watchdog_task=&data; data.enabled=true;
 data.pet_time=9360; data.bark_time=11000; data.pet_timer.pending=true;
 data.user_pet_enabled=true; data.user_pet_timer.pending=true;
 log_errors=resets=disables=enables=connects=disconnects=event_count=0; events[0]=0;
 reset_failure=-1; disable_error=enable_error=connect_error=disconnect_error=0;
 pin_ok=hw_enabled=hw_connected=scm_ready=true; missing_usb=missing_wdt=false;
}
static void balanced(void) {
 assert(!owner.refs && !usbdev.refs && !wdtdev.refs && !gadget.dev.refs);
 assert(!usbdev.locked && !wdtdev.locked && !data.disable_lock.held && !data.freeze_lock);
}
static void restored(void) {
 balanced(); assert(hw_enabled && hw_connected && data.enabled && !data.freeze_in_progress);
 assert(data.pet_timer.pending && data.user_pet_timer.pending);
}
int main(void) {
 struct qkx_usb u={0}; struct qkx_watchdog w={0};
 reset(); assert(!qkx_usb_get(&u,&usbdev)); assert(!qkx_watchdog_get(&w,&wdtdev,false,false));
 assert(!qkx_usb_disconnect(&u)); assert(!qkx_watchdog_prepare(&w)); assert(!qkx_watchdog_finish(&w,false));
 assert(!hw_connected && !hw_enabled && data.freeze_in_progress && !data.pet_timer.pending);
 assert(!qkx_platform_abort(&u,&w,0)); assert(!strcmp(events,"DRXERC")); restored();
 assert(!qkx_platform_abort(&u,&w,0)); balanced(); /* cleanup is idempotent */
 reset(); assert(!qkx_usb_get(&u,&usbdev)); disconnect_error=-EIO;
 assert(qkx_usb_disconnect(&u)==-EIO && !hw_connected);
 assert(qkx_platform_abort(&u,&w,-EIO)==-EIO && connects==1); restored();
 reset(); gadget.connected=false; hw_connected=false; assert(!qkx_usb_get(&u,&usbdev));
 assert(!qkx_usb_disconnect(&u)); assert(!qkx_platform_abort(&u,&w,0));
 assert(!connects && !disconnects && !hw_connected); balanced();
 reset(); assert(!qkx_usb_get(&u,&usbdev)); assert(!qkx_usb_disconnect(&u)); connect_error=-EACCES;
 assert(qkx_platform_abort(&u,&w,-EINVAL)==-EINVAL && log_errors==1); balanced();
 reset(); assert(!qkx_usb_get(&u,&usbdev)); assert(!qkx_usb_disconnect(&u)); connect_error=-EACCES;
 assert(qkx_platform_abort(&u,&w,0)==-EACCES); balanced();
 reset(); assert(!qkx_usb_get(&u,&usbdev)); usbdev.data=NULL;
 assert(qkx_usb_disconnect(&u)==-ENODEV && !disconnects); assert(!qkx_platform_abort(&u,&w,0)); balanced();
 reset(); assert(!qkx_usb_get(&u,&usbdev)); assert(!qkx_usb_disconnect(&u)); usbdev.driver=NULL;
 assert(qkx_platform_abort(&u,&w,0)==-ENODEV && !connects); balanced();
 reset(); assert(!qkx_watchdog_get(&w,&wdtdev,false,false)); reset_failure=1;
 assert(qkx_watchdog_prepare(&w)==-ETIMEDOUT && !disables);
 assert(qkx_platform_abort(&u,&w,-ETIMEDOUT)==-ETIMEDOUT); restored();
 reset(); assert(!qkx_usb_get(&u,&usbdev)); assert(!qkx_watchdog_get(&w,&wdtdev,false,false));
 assert(!qkx_usb_disconnect(&u)); disable_error=-EIO;
 assert(qkx_watchdog_prepare(&w)==-EIO && !hw_enabled);
 assert(qkx_platform_abort(&u,&w,-EIO)==-EIO && enables==1 && connects==1); restored();
 reset(); assert(!qkx_watchdog_get(&w,&wdtdev,false,false)); assert(!qkx_watchdog_prepare(&w));
 enable_error=-EACCES; assert(qkx_platform_abort(&u,&w,0)==-EACCES && log_errors>=1); balanced();
 assert(data.pet_timer.pending && !data.freeze_in_progress);
 reset(); assert(!qkx_usb_get(&u,&usbdev)); assert(!qkx_watchdog_get(&w,&wdtdev,false,false));
 assert(!qkx_usb_disconnect(&u)); assert(!qkx_watchdog_prepare(&w));
 enable_error=-EACCES; connect_error=-ENODEV; reset_failure=2;
 assert(qkx_platform_abort(&u,&w,-EIO)==-EIO && connects==1 && log_errors>=3); balanced();
 reset(); assert(!qkx_watchdog_get(&w,&wdtdev,true,false)); assert(!qkx_watchdog_prepare(&w));
 assert(!qkx_watchdog_finish(&w,true) && !disables && hw_enabled);
 assert(!qkx_platform_abort(&u,&w,0) && !enables); restored();
 reset(); assert(!qkx_watchdog_get(&w,&wdtdev,true,false)); assert(!qkx_watchdog_prepare(&w));
 disable_error=-EIO; assert(qkx_watchdog_finish(&w,false)==-EIO);
 assert(qkx_platform_abort(&u,&w,-EIO)==-EIO && enables==1); restored();
 reset(); assert(!qkx_watchdog_get(&w,&wdtdev,true,false)); assert(!qkx_watchdog_prepare(&w));
 reset_failure=2; assert(qkx_watchdog_finish(&w,true)==-ETIMEDOUT);
 assert(qkx_platform_abort(&u,&w,-ETIMEDOUT)==-ETIMEDOUT); restored();
 reset(); assert(qkx_watchdog_get(&w,&wdtdev,false,true)==-EOPNOTSUPP); balanced();
 assert(!disables && !resets);
 reset(); data.enabled=false; assert(qkx_watchdog_get(&w,&wdtdev,false,false)==-EOPNOTSUPP); balanced();
 reset(); assert(!qkx_watchdog_get(&w,&wdtdev,false,false)); data.freeze_in_progress=true;
 assert(qkx_watchdog_prepare(&w)==-EBUSY); assert(!qkx_platform_abort(&u,&w,0));
 assert(data.freeze_in_progress && !resets); balanced();
 reset(); assert(!qkx_watchdog_get(&w,&wdtdev,false,false)); assert(!qkx_watchdog_prepare(&w));
 assert(qkx_watchdog_prepare(&w)==-EBUSY); assert(!qkx_platform_abort(&u,&w,0)); restored();
 reset(); assert(!qkx_watchdog_get(&w,&wdtdev,false,false)); assert(!qkx_watchdog_prepare(&w));
 wdtdev.data=NULL; assert(qkx_platform_abort(&u,&w,0)==-ENODEV); balanced();
 reset(); pin_ok=false; assert(qkx_usb_get(&u,&usbdev)==-ENODEV);
 assert(qkx_watchdog_get(&w,&wdtdev,false,false)==-EOPNOTSUPP); balanced();
 reset(); assert(!qkx_platform_preflight()); restored();
 assert(!resets && !disables && !enables && !connects && !disconnects);
 reset(); scm_ready=false; assert(qkx_platform_preflight()==-ENODEV); balanced();
 reset(); missing_usb=true; assert(qkx_platform_preflight()==-ENODEV); balanced();
 reset(); missing_wdt=true; assert(qkx_platform_preflight()==-ENODEV); balanced();
 reset(); data.enabled=false; assert(qkx_platform_preflight()==-EOPNOTSUPP); balanced();
 assert(!resets && !disables && !enables && !connects && !disconnects);
 puts("PASS: read-only preflight success/failures without hardware callbacks");
 puts("PASS: USB partial failure/reconnect, original disconnected state, watchdog callback failures, timer restart, reverse rollback order, first-error retention, cleanup errors, driver detach, references/locks, unsupported timing");
}
'''
with tempfile.TemporaryDirectory() as d:
    d=Path(d)
    (d/'test.c').write_text(shim+stripped(root/'module/quest3-platform.h')+stripped(root/'module/quest3-platform.c')+tests)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation','-fsanitize=address,undefined','-g',str(d/'test.c'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test')],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
