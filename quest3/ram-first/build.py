#!/usr/bin/env python3
"""Build deterministic newc initramfs from a supplied static ARM64 BusyBox.
Does not boot, flash, mount disks or choose physical staging addresses.
"""
import argparse, gzip, hashlib, json, struct
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--busybox', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a=p.parse_args()
b=a.busybox.read_bytes()
if len(b)<64 or b[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',b,18)[0]!=183:
    p.error('BusyBox must be little-endian ELF64 AArch64')
if struct.unpack_from('<H',b,16)[0]!=2:
    p.error('BusyBox must be an executable ELF')
phoff=struct.unpack_from('<Q',b,32)[0]
ents,num=struct.unpack_from('<HH',b,54)
if not num or ents<56 or phoff+ents*num>len(b): p.error('invalid ELF program headers')
for i in range(num):
    kind=struct.unpack_from('<I',b,phoff+i*ents)[0]
    if kind in (2,3): p.error('BusyBox must be static: PT_DYNAMIC/PT_INTERP found')
archive=bytearray()
def entry(name,mode,data=b'',major=0,minor=0):
    fields=[1,mode,0,0,1,0,len(data),0,0,major,minor,len(name.encode())+1,0]
    archive.extend(b'070701'+''.join(f'{x:08x}' for x in fields).encode())
    archive.extend(name.encode()+b'\0')
    archive.extend(b'\0'*(-len(archive)%4))
    archive.extend(data)
    archive.extend(b'\0'*(-len(archive)%4))
for directory in ['bin','sbin','dev','proc','sys','tmp','config','root']:
    entry(directory,0o40755)
entry('dev/console',0o20600,major=5,minor=1)
entry('dev/null',0o20666,major=1,minor=3)
entry('bin/busybox',0o100755,b)
entry('init',0o100755,Path(__file__).with_name('init').read_bytes())
entry('TRAILER!!!',0)
archive.extend(b'\0'*(-len(archive)%512))
result=gzip.compress(bytes(archive),mtime=0)
with a.out.open('xb') as f: f.write(result)
print(json.dumps({'output':str(a.out),'sha256':hashlib.sha256(result).hexdigest(),
 'busybox_sha256':hashlib.sha256(b).hexdigest(),'bytes':len(result),
 'hardware_tested':False,'retained_log_region_validated':False},indent=2))
