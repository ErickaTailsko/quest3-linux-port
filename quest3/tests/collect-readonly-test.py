#!/usr/bin/env python3
"""Exercise the collector against a fake adb executable, never a device."""
from pathlib import Path
import importlib.util, json, os, subprocess, tempfile
r=Path(__file__).resolve().parents[1]; collector=r/'device-tools/collect-readonly.py'
spec=importlib.util.spec_from_file_location('collector',collector); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
fake=r'''#!/usr/bin/env python3
import gzip,json,os,shlex,sys
from pathlib import Path
a=sys.argv[1:]
with open(os.environ['ADB_LOG'],'a') as f:f.write(json.dumps(a)+'\n')
if a==['devices']:
 print('List of devices attached')
 print('TEST1\t'+('unauthorized' if os.environ.get('UNAUTHORIZED') else 'device'))
 if os.environ.get('MULTIPLE'):print('TEST2\tdevice')
 sys.exit(0)
assert a[:3]==['-s','TEST1','exec-out'],a
cmd=a[3] if len(a)==4 else a[5]
if len(a)!=4:assert a[3:5]==['su','-c'],a
assert cmd in json.loads(os.environ['ALLOWED']),cmd
if os.environ.get('FAIL_LOG') and cmd=='dmesg':
 print('Permission denied',file=sys.stderr);sys.exit(1)
if cmd=='cat /proc/config.gz':sys.stdout.buffer.write(gzip.compress(b'CONFIG_CFI_CLANG=y\n'))
else:print('fake diagnostic')
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp); adb=p/'adb';adb.write_text(fake);adb.chmod(0o755)
 env={**os.environ,'ADB_LOG':str(p/'calls.jsonl'),'ALLOWED':json.dumps(list(m.COMMANDS.values()))}
 def run(name,*extra,**changes):
  return subprocess.run(['python3',str(collector),'--adb',str(adb),'--out',str(p/name),*extra],env={**env,**changes},capture_output=True,text=True)
 assert run('ok').returncode==0
 assert (p/'ok/device-config.txt').read_text()=='CONFIG_CFI_CLANG=y\n'
 manifest=json.loads((p/'ok/manifest.json').read_text());assert not manifest['device_modified'] and not manifest['root_reads']
 assert len(manifest['records'])==len(m.COMMANDS)
 assert run('root','--root').returncode==0
 assert run('partial',FAIL_LOG='1').returncode==2
 report=json.loads((p/'partial/manifest.json').read_text());assert report['records']['kernel-log.txt']['returncode']==1
 assert (p/'partial/device-config.txt').exists()
 assert run('unauthorized',UNAUTHORIZED='1').returncode!=0 and not (p/'unauthorized').exists()
 assert run('ambiguous',MULTIPLE='1').returncode!=0 and not (p/'ambiguous').exists()
 assert run('selected','--serial','TEST1',MULTIPLE='1').returncode==0
 assert run('absent','--serial','TEST9').returncode!=0 and not (p/'absent').exists()
 old=(p/'ok/manifest.json').read_bytes();assert run('ok').returncode!=0
 assert (p/'ok/manifest.json').read_bytes()==old
print('PASS: diagnostic collector read-only whitelist, device selection, root reads, gzip, partial errors and no-overwrite (fake adb only)')
