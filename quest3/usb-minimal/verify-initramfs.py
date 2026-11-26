#!/usr/bin/env python3
"""Independent newc parser and ARM64 userspace smoke checks (not a boot test)."""
import argparse, gzip, hashlib, json, stat, struct, subprocess, shutil
from pathlib import Path
r=Path(__file__).resolve().parent
archive=r/'quest3-usb2-minimal.cpio.gz'
data=gzip.decompress(archive.read_bytes())
pos=0; entries={}
while True:
    assert data[pos:pos+6]==b'070701',pos
    fields=[int(data[pos+6+i*8:pos+14+i*8],16) for i in range(13)]
    pos+=110
    ino,mode,uid,gid,nlink,mtime,size,devmaj,devmin,rmaj,rmin,namesize,check=fields
    name=data[pos:pos+namesize]; assert name[-1:]==b'\0'
    name=name[:-1].decode(); pos=(pos+namesize+3)&~3
    content=data[pos:pos+size]; assert len(content)==size
    pos=(pos+size+3)&~3
    assert name not in entries and not name.startswith('/') and '..' not in name.split('/')
    assert uid==gid==mtime==0
    if name=='TRAILER!!!':break
    entries[name]=(mode,rmaj,rmin,content)
assert not any(data[pos:]) and len(data)%512==0
assert len(entries)==12
assert entries['dev/console'][:3]==(0o20600,5,1)
assert entries['dev/null'][:3]==(0o20666,1,3)
for name,source in [('init','init'),('bin/busybox','busybox-arm64')]:
    assert entries[name][0]==0o100755
    assert entries[name][3]==(r/source).read_bytes()
b=entries['bin/busybox'][3]
assert b[:6]==b'\x7fELF\x02\x01' and struct.unpack_from('<H',b,18)[0]==183
ph=struct.unpack_from('<Q',b,32)[0];ents,num=struct.unpack_from('<HH',b,54)
assert all(struct.unpack_from('<I',b,ph+i*ents)[0] not in (2,3) for i in range(num))
parser=argparse.ArgumentParser()
parser.add_argument('--qemu', default=str(r/'crossroot/usr/bin/qemu-aarch64') if (r/'crossroot/usr/bin/qemu-aarch64').exists() else shutil.which('qemu-aarch64'))
args=parser.parse_args()
if not args.qemu: parser.error('Install qemu-user or supply --qemu PATH')
q=Path(args.qemu)
def run(*args):
    return subprocess.check_output([str(q),str(r/'busybox-arm64'),*args],stderr=subprocess.STDOUT,text=True,timeout=20)
apps=set(run('--list').splitlines())
required=set('sh mount mkdir sleep uname ln ifconfig telnetd dmesg kill cat echo printf ls cp tar gzip sha256sum head tail grep ps ping readlink test ['.split())
assert required<=apps,required-apps
run('sh','-n',str(r/'init'))
assert run('sh','-c','n=0; while [ "$n" -lt 3 ]; do n=$((n+1)); done; printf "%s\\n" "$n"')=='3\n'
helptext=run('--help','telnetd');assert '-b' in helptext and '-l' in helptext and '-F' in helptext
result={'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
 'busybox_sha256':hashlib.sha256(b).hexdigest(),'archive_bytes':archive.stat().st_size,
 'busybox_bytes':len(b),'cpio_entries':list(entries),'applets':sorted(apps),
 'static_arm64':True,'init_syntax_in_arm64_emulator':'passed',
 'shell_arithmetic_and_tests':'passed','telnetd_required_options':'passed',
 'boot_tested':False,'USB_hardware_tested':False,'retained_log_validated':False}
if (r/'verification.json').exists():
    previous=json.loads((r/'verification.json').read_text())
    for key in ['deterministic_archive_rebuild','invalid_binary_rejection','dynamic_binary_rejection','output_overwrite_rejection']:
        if key in previous: result[key]=previous[key]
(r/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='applets'},indent=2))
