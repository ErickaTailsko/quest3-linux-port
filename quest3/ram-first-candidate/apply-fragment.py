#!/usr/bin/env python3
"""Prepare a new output config from a supplied base. Does not edit kernel source."""
from pathlib import Path
import argparse
p=argparse.ArgumentParser()
p.add_argument('--base',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
fragment=Path(__file__).with_name('usb-builtin.fragment').read_text().splitlines()
settings={}
for l in fragment:
 if l.startswith('CONFIG_') and '=' in l:
  k,v=l.split('=',1);settings[k]=v
base=a.base.read_text().splitlines()
result=[]
for l in base:
 key=l.split('=',1)[0] if l.startswith('CONFIG_') else l[2:-11] if l.startswith('# CONFIG_') and l.endswith(' is not set') else None
 if key not in settings:result.append(l)
result.extend(k+'='+v for k,v in sorted(settings.items()))
a.out.parent.mkdir(parents=True,exist_ok=True)
with a.out.open('x') as f:f.write('\n'.join(result)+'\n')
print('Config prepared; run olddefconfig with the matching LLVM toolchain next:',a.out)
