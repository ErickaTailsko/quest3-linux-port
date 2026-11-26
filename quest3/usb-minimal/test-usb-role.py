from pathlib import Path
import subprocess,tempfile
p=Path(__file__).parent
prefix=r'''
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#include <errno.h>
#include <stdio.h>
#define USB_DR_MODE_OTG 3
#define USB_DR_MODE_HOST 1
#define USB_DR_MODE_PERIPHERAL 2
#define DWC3_ID_GROUND 0
#define IIO 1
#define REMOTE_PROC 2
#define PSY 3
#define IS_ERR(x) false
#define fallthrough __attribute__((fallthrough))
#define dev_dbg(...) ((void)0)
struct device_node {bool role,extcon,iio,host,none;};
struct device {struct device_node *of_node;};
struct notifier {int (*notifier_call)(void);};
struct regulator {int unused;};
struct dwc3_msm {struct device *dev;int apsd_source;bool vbus_active;struct regulator *dpdm_reg;struct notifier dpdm_nb;void *role_switch;void *extcon;int sm_usb_wq,sm_work,id_state,dr_mode;};
struct platform_device {struct dwc3_msm *data;struct device dev;};
static int notifications,extcon_calls,extcon_error;
static struct dwc3_msm *platform_get_drvdata(struct platform_device*p){return p->data;}
static bool of_property_read_bool(struct device_node*n,const char*p){if(!strcmp(p,"extcon"))return n->extcon;if(!strcmp(p,"qcom,default-mode-host"))return n->host;if(!strcmp(p,"qcom,default-mode-none"))return n->none;return false;}
static void *of_get_property(struct device_node*n,const char*p,void*unused){(void)unused;return (!strcmp(p,"usb-role-switch")?n->role:n->iio)?n:0;}
static int dwc3_msm_extcon_register(struct dwc3_msm*m){(void)m;extcon_calls++;return extcon_error;}
static struct regulator *devm_regulator_get_optional(struct device*d,const char*n){(void)d;(void)n;return 0;}
static int regulator_is_enabled(struct regulator*r){(void)r;return 0;}
static int dwc_dpdm_cb(void){return 0;}
static void regulator_register_notifier(struct regulator*r,struct notifier*n){(void)r;(void)n;}
static void queue_delayed_work(int w,int*s,int delay){(void)w;(void)s;(void)delay;}
static void dwc3_ext_event_notify(struct dwc3_msm*m){(void)m;notifications++;}
'''
main=r'''
int main(void){
struct device_node node={0};struct device dev={&node};struct dwc3_msm m={.dev=&dev,.dr_mode=USB_DR_MODE_PERIPHERAL,.id_state=1};struct platform_device p={.data=&m};
assert(dwc3_msm_check_extcon_prop(&p)==0);assert(m.apsd_source==PSY&&m.vbus_active&&notifications==1&&!extcon_calls&&m.id_state==1);
node.role=true;m.role_switch=&node;m.vbus_active=false;notifications=0;assert(dwc3_msm_check_extcon_prop(&p)==0);assert(m.apsd_source==REMOTE_PROC&&!m.vbus_active&&!notifications);
node.role=false;m.role_switch=0;m.dr_mode=USB_DR_MODE_HOST;assert(dwc3_msm_check_extcon_prop(&p)==0);assert(m.id_state==DWC3_ID_GROUND&&!m.vbus_active);
node.extcon=true;extcon_error=-EIO;notifications=0;assert(dwc3_msm_check_extcon_prop(&p)==-EIO);assert(extcon_calls==1&&!notifications);
puts("PASS: real driver role function; peripheral defaults without UCSI events, role-switch waits for events, host counterexample, extcon failure");
}
'''
with tempfile.TemporaryDirectory() as d:
 f=Path(d)/'test.c';f.write_text(prefix+(p/'driver-role-function.c').read_text()+main)
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(f),'-o',d+'/test'],check=True)
 subprocess.run([d+'/test'],check=True)
