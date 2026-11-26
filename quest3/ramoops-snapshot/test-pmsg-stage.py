#!/usr/bin/env python3
"""Model actual stage/verification scripts; no device or reboot is used."""
import argparse
import base64
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

root = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('--dtb', type=Path, default=root.parent / 'usb-minimal/quest3-usb2-peripheral.private.dtb')
args = ap.parse_args()
def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), root / (name + '.py'))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
stage = load('stage-pmsg-test'); checker = load('check-pmsg-baseline')
boot = '12345678-1234-1234-1234-123456789abc'
for mode in ['valid', 'lost-write-response', 'bad-payload-hash']:
    files = {}; calls = []; writes = []; body = bytearray(0x20000 - 12)
    def adb(argv, **kwargs):
        command = shlex.split(argv[-1])[2]; calls.append(command)
        if command == 'id': stdout = b'uid=0(root)'
        elif command.startswith('cat /proc/'): stdout = boot.encode()
        elif command == 'test -c /dev/pmsg0': stdout = b''
        elif command.startswith('umask '): files[command.split()[-1]] = bytearray(); stdout = b''
        elif command.startswith('printf '):
            data = base64.b64decode(re.search(r'printf %s (\S+) \|', command)[1])
            target = re.search(r'of=(\S+)', command)[1]
            offset = int(re.search(r'seek=(\d+)', command)[1]) * 4096
            buffer = files[target]
            if len(buffer) < offset + len(data): buffer.extend(bytes(offset + len(data) - len(buffer)))
            buffer[offset:offset + len(data)] = data; stdout = b''
        elif command.startswith('sha256sum '):
            digest = hashlib.sha256(files[command.split()[-1]]).hexdigest()
            stdout = (digest if mode != 'bad-payload-hash' else '0' * 64).encode()
        elif command.startswith('test -c /dev/pmsg0 && cat '):
            payload = files[shlex.split(command)[5]]; writes.append(bytes(payload))
            body[2726:2726 + len(payload)] = payload
            if mode == 'lost-write-response':
                raise subprocess.TimeoutExpired(argv, 20)
            stdout = b''
        elif command.startswith('rm -f '): files.pop(command.split()[-1], None); stdout = b''
        else: raise AssertionError(command)
        return subprocess.CompletedProcess(argv, 0, stdout, b'')
    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / 'test'; capture = Path(tmp) / 'capture'; capture.mkdir()
        with patch.object(stage.subprocess, 'run', side_effect=adb), patch.object(stage.time, 'sleep'), patch('builtins.print'):
            if mode == 'valid': stage.stage(test)
            else:
                try: stage.stage(test)
                except (RuntimeError, subprocess.TimeoutExpired): pass
                else: raise AssertionError('expected injected failure')
        meta = json.loads((test / 'test.json').read_text())
        if mode == 'bad-payload-hash':
            assert not writes and not meta['pmsg_write_attempted']; continue
        assert len(writes) == 1 and not files
        assert writes[0] == bytes(65536) + meta['marker'].encode() + b'\n'
        assert meta['status'] == ('write-returned-success' if mode == 'valid' else 'write-result-uncertain')
        blob = bytearray(0x90000); blob[0x70000 + 12:0x90000] = body
        size = 2726 + len(writes[0]); struct.pack_into('<III', blob, 0x70000, 0x43474244, size, size)
        (capture / 'ramoops.bin').write_bytes(blob)
        manifest = {'status': 'verified', 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(), 'boot_id': boot}
        (capture / 'manifest.json').write_text(json.dumps(manifest))
        verified = checker.check(test, capture, args.dtb)
        assert verified['baseline_marker_verified'] and verified['marker_offset_in_pmsg_data'] == 2726 + 65536
        assert not verified['retention_validated'] and verified['pmsg_physical_base'] == '0xbfa70000'
        manifest['boot_id'] = 'aaaaaaaa-1234-1234-1234-123456789abc'
        (capture / 'manifest.json').write_text(json.dumps(manifest))
        try: checker.check(test, capture, args.dtb)
        except ValueError: pass
        else: raise AssertionError('changed boot baseline accepted')
        assert not any(re.search(r'\b(insmod|reboot|setprop)\b', call) for call in calls)
print('PASS padded payload, exact-once marker write despite lost response, temporary hash gate/cleanup, baseline offset/hash/boot validation; retention remains false')
