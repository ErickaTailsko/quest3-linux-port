#!/usr/bin/env python3
"""End-to-end collector checks with synthetic FDT and fake ADB only."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import struct
import shlex
import subprocess
import sys
import tempfile

collector = Path(__file__).with_name('collect-memory-maps.py')
spec = importlib.util.spec_from_file_location('collector', collector)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def dtb():
    strings = bytearray()
    def prop(name, value):
        offset = len(strings)
        strings.extend(name.encode() + b'\0')
        return struct.pack('>III', 3, len(value), offset) + value + bytes(-len(value) % 4)
    def node(name, props, children=b''):
        encoded = name.encode() + b'\0'
        return (struct.pack('>I', 1) + encoded + bytes(-len(encoded) % 4) +
                b''.join(prop(key, value) for key, value in props.items()) + children + struct.pack('>I', 2))
    cells = {'#address-cells': struct.pack('>I', 2), '#size-cells': struct.pack('>I', 2)}
    children = node('reserved-memory', {**cells, 'ranges': b''})
    children += node('memory', {'device_type': b'memory\0', 'reg': struct.pack('>QQ', 0x100000000, 128*1024*1024)})
    tree = node('', {**cells, 'compatible': b'oculus,eureka\0qcom,anorak\0'}, children) + struct.pack('>I', 9)
    total = 56 + len(tree) + len(strings)
    return struct.pack('>10I', 0xd00dfeed, total, 56, 56+len(tree), 40, 17, 16, 0, len(strings), len(tree)) + bytes(16) + tree + strings


fake = r'''#!/usr/bin/env python3
import json,os,shlex,sys
from pathlib import Path
a=sys.argv[1:];mode=os.environ.get('MODE','ok')
def read_command(args):
 if len(args)!=4:return None
 tokens=shlex.split(args[3])
 if tokens[:2]==['su','-c']:
  assert len(tokens)==3,tokens
  return tokens[2]
 return args[3]
with open(os.environ['ADB_LOG'],'a') as f:f.write(json.dumps(a)+'\n')
if a==['devices']:
 print('List of devices attached')
 if mode!='absent':print('FAKE1\t'+('unauthorized' if mode=='unauthorized' else 'device'))
 if mode=='multiple':print('FAKE2\tdevice')
 sys.exit(0)
assert a[:3]==['-s','FAKE1','exec-out'],a
assert len(a)==4,a
command=read_command(a);assert command in json.loads(os.environ['ALLOWED']),command
if command=='cat /proc/sys/kernel/random/boot_id':
 if mode=='invalid-boot':print('not-a-boot-token');sys.exit(0)
 log=Path(os.environ['ADB_LOG']).read_text()
 count=sum(read_command(json.loads(line))==command for line in log.splitlines())
 print('00000000-0000-0000-0000-'+('000000000002' if mode=='boot-change' and count==2 else '000000000001'))
elif command=='id':print('uid=2000(shell)' if mode=='not-root' else 'uid=0(root) gid=0(root)')
elif command=='uname -r':print('unexpected' if mode=='release' else '5.10.246-gd7102a837402')
elif command=='getconf PAGESIZE':print('16384' if mode=='page-size' else '4096')
elif command=='cat /proc/device-tree/compatible':sys.stdout.buffer.write(b'wrong-board\0' if mode=='compatible' else b'oculus,eureka\0qcom,anorak\0')
elif command=='cat /sys/firmware/fdt':sys.stdout.buffer.write(b'broken' if mode=='dtb' else Path(os.environ['DTB']).read_bytes()+(b'noise' if mode=='dtb-noise' else b''))
elif command=='cat /proc/iomem':
 if mode=='failed-read':print('denied',file=sys.stderr);sys.exit(1)
 print('00000000-00000000 : System RAM' if mode=='redacted' else '100000000-107ffffff : System RAM')
elif command=='cat /proc/zoneinfo':print('Node 0, zone Normal\n  pages free 1234')
elif command=='cat /proc/pagetypeinfo':print('Page block order: '+('9' if mode=='pageblock' else '10')+'\nPages per block: '+('512' if mode=='pages-per-block' else '1024'))
else:raise AssertionError(command)
'''

with tempfile.TemporaryDirectory() as temp:
    p = Path(temp)
    adb = p / 'adb'
    adb.write_text(fake)
    adb.chmod(0o755)
    (p / 'fixture.dtb').write_bytes(dtb())
    env = {**os.environ, 'ADB_LOG': str(p/'calls.jsonl'), 'DTB': str(p/'fixture.dtb'),
           'ALLOWED': json.dumps(list(module.COMMANDS.values()))}

    def run(name, *extra, mode='ok'):
        (p/'calls.jsonl').write_text('')
        return subprocess.run([sys.executable, str(collector), '--adb', str(adb), '--out', str(p/name), *extra],
                              capture_output=True, text=True, env={**env, 'MODE': mode})

    assert run('ok', '--root').returncode == 0
    evidence = json.loads((p/'ok/manifest.json').read_text())
    assert evidence['validation']['same_boot'] and evidence['status'] == 'captured-and-validated'
    assert not evidence['live_metadata_atomic'] and not evidence['boot_ready']
    assert not evidence['device_writes_requested'] and not evidence['cpu_pause_requested']
    assert len(evidence['records']) == len(module.COMMANDS)
    assert (p/'ok').stat().st_mode & 0o777 == 0o700
    for name,record in evidence['records'].items():
        assert hashlib.sha256((p/'ok'/name).read_bytes()).hexdigest() == record['sha256']
        assert hashlib.sha256((p/'ok'/(name+'.stderr')).read_bytes()).hexdigest() == record['stderr_sha256']
    assert (p/'ok/live.dtb').read_bytes() == dtb()
    assert '00000000-0000' not in (p/'ok/manifest.json').read_text()
    assert 'FAKE1' not in (p/'ok/manifest.json').read_text()
    calls = [json.loads(line) for line in (p/'calls.jsonl').read_text().splitlines()]
    assert len(calls) == 1 + len(module.COMMANDS)
    assert all(len(call)==4 and shlex.split(call[3])[:2] == ['su', '-c'] for call in calls[1:])
    assert [shlex.split(call[3])[2] for call in calls[1:]] == list(module.COMMANDS.values())
    assert run('unprivileged').returncode == 0
    old = (p/'ok/manifest.json').read_bytes()
    assert run('ok').returncode == 2 and (p/'ok/manifest.json').read_bytes() == old
    assert len((p/'calls.jsonl').read_text().splitlines()) == 1  # enumeration only
    for mode in ['absent', 'unauthorized', 'multiple']:
        assert run(mode, mode=mode).returncode == 2 and not (p/mode).exists()
    assert run('selected', '--serial', 'FAKE1', mode='multiple').returncode == 0
    assert run('bad-selection', '--serial', 'FAKE9').returncode == 2 and not (p/'bad-selection').exists()
    for mode in ['boot-change', 'invalid-boot', 'release', 'page-size', 'dtb', 'dtb-noise',
                 'compatible', 'failed-read', 'redacted', 'pageblock', 'pages-per-block', 'not-root']:
        result = run(mode, '--root', mode=mode)
        assert result.returncode == 2, (mode, result.stdout, result.stderr)
        report = json.loads((p/mode/'manifest.json').read_text())
        assert report['status'] == 'rejected' and report['validation']['errors']
        assert 'boot-after.txt' in report['records']
    assert not json.loads((p/'boot-change/manifest.json').read_text())['validation']['same_boot']

    def timeout_runner(argv, **kwargs):
        if argv[-1] == "su -c 'cat /proc/zoneinfo'":
            raise subprocess.TimeoutExpired(argv, 30, output=b'partial zone', stderr=b'partial error')
        return subprocess.run(argv, **kwargs, env=env)

    report = module.collect(p/'timeout', str(adb), root=True, runner=timeout_runner)
    assert report['status'] == 'rejected'
    assert report['records']['zoneinfo.txt']['error'] == 'timeout; not retried'
    assert (p/'timeout/zoneinfo.txt').read_bytes() == b'partial zone'
    assert report['records']['boot-after.txt']['returncode'] == 0

    def launch_error_runner(argv, **kwargs):
        if argv[-1] == 'cat /proc/zoneinfo':
            raise OSError('fake launch failure')
        return subprocess.run(argv, **kwargs, env=env)

    report = module.collect(p/'launch-error', str(adb), runner=launch_error_runner)
    assert report['status'] == 'rejected'
    assert report['records']['zoneinfo.txt']['error'] == 'could not launch ADB; not retried'
    assert report['records']['boot-after.txt']['returncode'] == 0

print('PASS private map collector: whitelist, binary DT, boot bracket, root opt-in, selection, no-overwrite, redaction, partial failure and timeout; fake ADB only')
