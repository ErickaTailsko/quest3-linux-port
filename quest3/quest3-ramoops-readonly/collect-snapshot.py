#!/usr/bin/env python3
"""Read an already loaded q3_ramoops_snapshot in verified ADB chunks.
Does not load/unload modules, write on the device, change services or reboot.
"""
import argparse
import base64
import hashlib
import json
import re
import shlex
import subprocess
import time
from pathlib import Path

REMOTE = '/sys/kernel/q3_ramoops_snapshot/data'
BLOCK = 16384

def collect(out, serial=None):
    out.mkdir(parents=True, exist_ok=False)
    prefix = ['adb'] + (['-s', serial] if serial else [])
    def read(command, root=True):
        remote = 'su -c ' + shlex.quote(command) if root else command
        result = subprocess.run(prefix + ['shell', remote], capture_output=True, timeout=20)
        if result.returncode or not result.stdout.strip():
            raise RuntimeError('ADB read failed (exit=' + str(result.returncode) + ')')
        return result.stdout
    report = {'status': 'incomplete', 'device_writes': False, 'reboot_requested': False}
    try:
        identity = read('id').decode(errors='replace')
        if not re.search(r'\buid=0\b', identity):
            raise RuntimeError('root identity not confirmed')
        boot = read('cat /proc/sys/kernel/random/boot_id', root=False).strip().decode()
        if not re.fullmatch(r'[0-9a-f-]{36}', boot):
            raise RuntimeError('invalid boot identity')
        size = int(read('wc -c ' + REMOTE).split()[0])
        expected = read('sha256sum ' + REMOTE).split()[0].decode()
        if not 4096 <= size <= 1048576 or size % 4096 or not re.fullmatch('[0-9a-f]{64}', expected):
            raise RuntimeError('invalid snapshot metadata')
        data = bytearray()
        total = (size + BLOCK - 1) // BLOCK
        for index in range(total):
            for attempt in range(3):
                try:
                    # sysfs bin reads can return at most PAGE_SIZE. Read four
                    # 4KiB records rather than assuming one full 16KiB read.
                    raw = read(f'dd if={REMOTE} bs=4096 skip={index * 4} count=4 2>/dev/null | base64')
                    chunk = base64.b64decode(b''.join(raw.split()), validate=True)
                    if len(chunk) != min(BLOCK, size - index * BLOCK):
                        raise ValueError('truncated chunk')
                    break
                except (RuntimeError, ValueError, subprocess.TimeoutExpired):
                    if attempt == 2:
                        raise RuntimeError('snapshot chunk failed: ' + str(index + 1))
                    time.sleep(1)
            data.extend(chunk)
            print(f'Block {index + 1}/{total}', flush=True)
        actual = hashlib.sha256(data).hexdigest()
        final_boot = read('cat /proc/sys/kernel/random/boot_id', root=False).strip().decode()
        final_hash = read('sha256sum ' + REMOTE).split()[0].decode()
        if actual != expected or final_hash != expected or final_boot != boot:
            raise RuntimeError('snapshot integrity or boot identity changed')
        (out / 'ramoops.bin').write_bytes(data)
        report.update(status='verified', bytes=size, sha256=actual, boot_id=boot,
                      note='Immutable exported copy; original live capture can race writers.')
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--serial')
    args = ap.parse_args()
    try:
        print(json.dumps(collect(args.out, args.serial), indent=2))
    except Exception as error:
        raise SystemExit('Collection incomplete: ' + str(error))
