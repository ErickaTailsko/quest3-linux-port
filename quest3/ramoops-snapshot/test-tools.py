#!/usr/bin/env python3
import base64
import argparse
import hashlib
import importlib.util
import json
import re
import shlex
import struct
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from fdtcheck import rewrite

root = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('--dtb', type=Path, default=root.parent / 'usb-minimal/quest3-usb2-peripheral.private.dtb')
args = ap.parse_args()
def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), root / (name + '.py'))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
decoder = module('analyze-snapshot'); collector = module('collect-snapshot')
dtb = args.dtb.read_bytes()
blob = bytearray(0x90000)
for off, name in [(0, 'dmesg'), (0x30000, 'console'), (0x50000, 'ftrace'), (0x70000, 'pmsg')]:
    sig = decoder.SIGNATURE ^ (decoder.VERSION if name == 'ftrace' else 0)
    struct.pack_into('<III', blob, off, sig, 0, 0)
marker = decoder.MARKERS[1]
blob[0x70000 + 12:0x70000 + 12 + len(marker)] = marker
report = decoder.analyze(bytes(blob), dtb)
assert report['regions'][-1]['markers'][0]['in_current_logical_ring'] is False
assert not report['retention_validated']
struct.pack_into('<II', blob, 0x70000 + 4, len(marker), len(marker))
assert decoder.analyze(bytes(blob), dtb)['regions'][-1]['markers'][0]['in_current_logical_ring']
struct.pack_into('<II', blob, 0x70000 + 4, 0x30000, 0x30000)
assert not decoder.analyze(bytes(blob), dtb)['regions'][-1]['header_valid']
capacity = 0x20000 - 12
blob[0x70000 + 12:0x90000] = bytes(capacity)
blob[0x90000 - 8:0x90000] = marker[:8]
blob[0x70000 + 12:0x70000 + 12 + len(marker) - 8] = marker[8:]
struct.pack_into('<II', blob, 0x70000 + 4, capacity - 8, capacity)
wrapped = decoder.analyze(bytes(blob), dtb)['regions'][-1]['markers'][0]
assert wrapped['in_current_logical_ring'] and wrapped['raw_offset'] is None
try:
    decoder.analyze(bytes(blob[:-1]), dtb)
except ValueError:
    pass
else:
    raise AssertionError('truncated snapshot accepted')

payload = bytes(range(256)) * 80
digest = hashlib.sha256(payload).hexdigest(); boot = '12345678-1234-1234-1234-123456789abc'
def scenario(mode):
    calls = []
    def adb(args, **kwargs):
        assert args[0] == 'adb' and args[1:3] == ['-s', 'test-device']
        remote = args[-1]
        command = shlex.split(remote)[2] if remote.startswith('su -c ') else remote
        calls.append(command)
        if command == 'id':
            stdout = b'uid=2000(shell)' if mode == 'not-root' else b'uid=0(root)'
        elif 'boot_id' in command:
            stdout = (boot if mode != 'boot-changed' or calls.count(command) == 1 else 'aaaaaaaa-1234-1234-1234-123456789abc').encode()
        elif command.startswith('wc -c '):
            stdout = str(len(payload)).encode()
        elif command.startswith('sha256sum '):
            stdout = (digest if mode != 'bad-hash' else '0' * 64).encode()
        elif command.startswith('dd if='):
            skip = int(re.search(r'skip=(\d+)', command)[1])
            assert 'bs=4096' in command and 'count=4' in command
            stdout = base64.b64encode(payload[skip * 4096:(skip + 4) * 4096])
            if mode == 'truncated': stdout = base64.b64encode(b'short')
            if mode == 'retry' and calls.count(command) == 1: stdout = b'error: closed'
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(args, 0, stdout, b'')
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / 'result'
        with patch.object(collector.subprocess, 'run', side_effect=adb), patch.object(collector.time, 'sleep'):
            if mode in ('valid', 'retry'):
                assert collector.collect(out, 'test-device')['status'] == 'verified'
                assert (out / 'ramoops.bin').read_bytes() == payload
                try: collector.collect(out, 'test-device')
                except FileExistsError: pass
                else: raise AssertionError('overwrote output')
            else:
                try: collector.collect(out, 'test-device')
                except RuntimeError: pass
                else: raise AssertionError('invalid transfer accepted')
                assert not (out / 'ramoops.bin').exists()
                assert json.loads((out / 'manifest.json').read_text())['status'] == 'incomplete'
        assert not any(x in '\n'.join(calls) for x in ['insmod', 'rmmod', 'reboot', 'setprop', '/dev/pmsg0'])
for mode in ['valid', 'retry', 'truncated', 'not-root', 'bad-hash', 'boot-changed']:
    scenario(mode)
print('PASS parser logical/residual marker distinction and invalid headers; collector retries, root, hash, boot identity, truncation and overwrite guards')
