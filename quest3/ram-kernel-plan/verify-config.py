#!/usr/bin/env python3
from pathlib import Path
import json
r=Path(__file__).resolve().parents[1]
def config(file):
 out={}
 for l in file.read_text().splitlines():
  if l.startswith('CONFIG_') and '=' in l:
   k,v=l.split('=',1);out[k]=v
  elif l.startswith('# CONFIG_') and l.endswith(' is not set'):
   out[l[2:-11]]='n'
 return out
base=config(r/'out/.config');target=config(r/'ram-first-kernel/.config')
req=(r/'ram-kernel-plan/usb-builtin.fragment').read_text().splitlines()+(r/'ram-first/required.config').read_text().splitlines()
for l in req:
 k,v=l.split('=');assert target.get(k,'n')==v,(k,target.get(k))
for key in ['USB_F_ECM','USB_U_ETHER','USB_DWC3','USB_GADGET','USB_ROLE_SWITCH','TYPEC_UCSI','CONFIGFS_FS']:
 assert target.get('CONFIG_'+key)=='y',key
security=['CFI_CLANG','CFI_CLANG_SHADOW','SHADOW_CALL_STACK','LTO_CLANG_FULL','MODVERSIONS']
assert all(target.get('CONFIG_'+k)=='y' for k in security)
changes={k:{'before':base.get(k,'n'),'after':target.get(k,'n')} for k in base.keys()|target.keys() if base.get(k,'n')!=target.get(k,'n')}
assert all(v['before'] in ('m','n') and v['after']=='y' for v in changes.values()),changes
rpt={'required_settings_accepted':True,'security_preserved':security,'effective_changes':dict(sorted(changes.items())),
 'image_boot_tested':False,'USB_hardware_tested':False,'firmware_handoff_validated':False}
(r/'ram-kernel-plan/config-verification.json').write_text(json.dumps(rpt,indent=2)+'\n')
print('PASS:',len(changes),'effective config changes; all are n/m -> y; required USB/initramfs settings and CFI/SCS/LTO preserved')
