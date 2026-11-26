#!/usr/bin/env python3
"""Controller model tests: mocked ADB only, including uncertain insertion cleanup."""
import hashlib
import base64
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

path = Path(__file__).with_name('collect-once.py')
spec = importlib.util.spec_from_file_location('query_controller',path)
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
lines=['descriptors_only=1 count=13 complete=13 owned=0 dma_safe=0 cpu_pause=0']
base=0xc0000000
for name,mib in m.SPECS:
    address=0x800000000 if name=='va_md_mem_region' else base
    size=mib*1024*1024
    lines.append(f'name={name} base=0x{address:x} size=0x{size:x} ops=1 priv=1 error=0')
    if name!='va_md_mem_region':base+=size
good='\n'.join(lines)+'\n'
assert len(m.validate_report(good))==13
for bad in [good.replace('complete=13','complete=12'),good.replace('ops=1','ops=0',1),
            good.replace('name=linux,cma','name=wrong',1),good.replace('base=0xc0000000','base=0xc0000001',1),
            good.replace('base=0x800000000','base=0x100000',1),
            good.replace('base=0xc2000000','base=0xc0000000',1)]:
    try:m.validate_report(bad)
    except ValueError:pass
    else:raise AssertionError('invalid report accepted')


class FakeADB:
    def __init__(self,mode='ok'):
        self.mode=mode;self.loaded=mode=='preexisting';self.uploaded=False
        self.calls=[];self.insertions=0;self.removals=0
        self.blob=bytearray()

    def __call__(self,argv,**kwargs):
        self.calls.append(argv)
        assert argv[:3]==['fake-adb','-s','TEST']
        stdout=b'';code=0
        assert len(argv)==5 and argv[3]=='exec-out'
        tokens=shlex.split(argv[4]);assert len(tokens)==3 and tokens[:2]==['su','-c']
        cmd=tokens[2]
        if cmd=='id':stdout=b'uid=0(root) gid=0(root)\n'
        elif cmd=='uname -r':stdout=b'5.10.246-gd7102a837402\n'
        elif cmd=='cat /proc/sys/kernel/random/boot_id':
            suffix=b'2' if self.mode=='boot-change' and self.insertions else b'1'
            stdout=b'00000000-0000-0000-0000-00000000000'+suffix+b'\n'
        elif cmd=='sha256sum /proc/config.gz':stdout=((m.EXPECTED_CONFIG_GZ if self.mode!='config' else '0'*64)+'  /proc/config.gz\n').encode()
        elif cmd=='sha256sum /sys/firmware/fdt':stdout=(m.EXPECTED_DTB+'  /sys/firmware/fdt\n').encode()
        elif cmd=='cat /sys/devices/system/cpu/online':stdout=b'0-5\n'
        elif cmd=='cat /proc/modules':stdout=(m.NAME+' 4096 0 - Live 0\n').encode() if self.loaded else b''
        elif cmd.startswith('if test -e '):
            match=re.fullmatch(r'if test -e ([^; ]+); then echo PRESENT; else echo ABSENT; fi',cmd);assert match
            target=match[1]
            assert target==m.SYSFS or target.startswith('/data/local/tmp/eris-rmem-')
            exists=self.loaded if target==m.SYSFS else self.uploaded
            stdout=b'PRESENT\n' if exists else b'ABSENT\n'
        elif cmd.startswith('sha256sum /data/local/tmp/eris-rmem-'):
            assert self.uploaded;stdout=(hashlib.sha256(self.blob).hexdigest()+'  module.ko\n').encode()
        elif cmd.startswith('umask 077; : > /data/local/tmp/eris-rmem-'):
            assert not self.uploaded;self.uploaded=True;self.blob=bytearray()
        elif cmd.startswith('printf %s '):
            match=re.fullmatch(r'printf %s ([A-Za-z0-9+/=]+) \| base64 -d \| dd of=/data/local/tmp/eris-rmem-[0-9a-f]+\.ko bs=4096 seek=(\d+) conv=notrunc 2>/dev/null',cmd);assert match
            assert self.uploaded
            chunk=base64.b64decode(match[1],validate=True);offset=int(match[2])*4096
            assert offset==len(self.blob) and len(chunk)<=4096
            self.blob.extend(chunk)
            if self.mode=='lost-chunk':raise subprocess.TimeoutExpired(argv,30)
        elif cmd.startswith('wc -c /data/local/tmp/eris-rmem-'):
            assert self.uploaded;stdout=(str(len(self.blob))+' module.ko\n').encode()
        elif cmd.startswith('insmod '):
            assert cmd.endswith(' inspect=1') and not self.loaded and self.uploaded
            self.insertions+=1;self.loaded=True
            if self.mode=='lost-response':raise subprocess.TimeoutExpired(argv,30)
        elif cmd=='cat '+m.SYSFS+'/report':
            assert self.loaded;stdout=(good if self.mode!='bad-report' else good.replace('complete=13','complete=0')).encode()
        elif cmd=='rmmod '+m.NAME:
            assert self.loaded;self.loaded=False;self.removals+=1
        elif cmd.startswith('rm -f /data/local/tmp/eris-rmem-'):
            assert self.uploaded;self.uploaded=False
        else:raise AssertionError('unexpected remote action: '+cmd)
        return subprocess.CompletedProcess(argv,code,stdout,b'')


with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);ko=root/'fixture.ko';ko.write_bytes(b'fake-reviewed-module'*501)
    m.EXPECTED=hashlib.sha256(ko.read_bytes()).hexdigest()
    fake=FakeADB();result=m.collect(root/'ok',ko,'TEST','fake-adb',fake)
    assert result['insertion_attempts']==1 and fake.insertions==1 and fake.removals==1
    assert result['cleanup_confirmed'] and result['temporary_cleanup_confirmed']
    assert not fake.loaded and not fake.uploaded and len(result['regions'])==13
    old=(root/'ok/operation.json').read_bytes();fake=FakeADB()
    try:m.collect(root/'ok',ko,'TEST','fake-adb',fake)
    except FileExistsError:pass
    else:raise AssertionError('existing evidence overwritten')
    assert not fake.calls and (root/'ok/operation.json').read_bytes()==old
    for mode in ['lost-response','bad-report','boot-change','preexisting','config','lost-chunk']:
        fake=FakeADB(mode)
        try:m.collect(root/mode,ko,'TEST','fake-adb',fake)
        except RuntimeError:pass
        else:raise AssertionError('unsafe state accepted: '+mode)
        report=json.loads((root/mode/'operation.json').read_text())
        assert fake.insertions<=1
        if mode in ['lost-response','bad-report']:
            assert fake.insertions==1 and fake.removals==1 and not fake.loaded and not fake.uploaded
            assert report['cleanup_confirmed'] and report['temporary_cleanup_confirmed']
        elif mode=='boot-change':
            assert fake.removals==0 and fake.loaded and 'cleanup_error' in report
        elif mode=='preexisting':
            assert fake.insertions==0 and fake.removals==0 and not fake.uploaded
        else:assert fake.insertions==0 and not fake.uploaded
    ko.write_bytes(b'not-reviewed');fake=FakeADB()
    try:m.collect(root/'bad-hash',ko,'TEST','fake-adb',fake)
    except ValueError:pass
    else:raise AssertionError('unreviewed binary accepted')
    assert not fake.calls and not (root/'bad-hash').exists()
    result=subprocess.run(['python3',str(path),'--module',str(ko),'--out',str(root/'no-ack'),'--serial','TEST','--adb','does-not-exist'],capture_output=True)
    assert result.returncode==2 and not (root/'no-ack').exists()
print('PASS descriptor controller: fixed constraints, quoting, consent gate, exact-once insertion, hashes, partial/uncertain cleanup and no cleanup across changed boot; mocks only')
