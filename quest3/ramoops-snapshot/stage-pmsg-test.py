#!/usr/bin/env python3
"""Write one padded marker through /dev/pmsg0. No reboot, module or raw mapping.
This consumes about 64KiB of the diagnostic PMSG ring. Preserve the prior capture.
Never retry the device-marker write after an uncertain ADB response.
"""
import argparse
import base64
import hashlib
import json
import re
import shlex
import subprocess
import time
import uuid
from pathlib import Path

def stage(out):
    out.mkdir(parents=True, exist_ok=False)
    token = uuid.uuid4().hex
    marker = 'Q3_RAW_RETENTION_' + token
    payload = bytes(65536) + marker.encode() + b'\n'
    temporary = '/data/local/tmp/q3-pmsg-test-' + token + '.bin'
    report = {'status': 'incomplete', 'marker': marker, 'padding_bytes': 65536,
              'payload_bytes': len(payload), 'payload_sha256': hashlib.sha256(payload).hexdigest(),
              'pmsg_write_attempted': False, 'reboot_requested': False,
              'modules_loaded': False, 'retention_validated': False}
    def run(command, retry=False, check=True):
        for attempt in range(3 if retry else 1):
            try:
                result = subprocess.run(['adb', 'shell', 'su -c ' + shlex.quote(command)],
                                        capture_output=True, timeout=20)
                if check and result.returncode:
                    raise RuntimeError('ADB command failed')
                return result
            except (RuntimeError, subprocess.TimeoutExpired):
                if not retry or attempt == 2:
                    raise
                time.sleep(1)
    try:
        if not re.search(rb'\buid=0\(', run('id', retry=True).stdout):
            raise RuntimeError('root identity not confirmed')
        boot = run('cat /proc/sys/kernel/random/boot_id', retry=True).stdout.strip().decode()
        if not re.fullmatch(r'[0-9a-f-]{36}', boot):
            raise RuntimeError('invalid boot identity')
        report['boot_id_before_write'] = boot
        run('test -c /dev/pmsg0')
        run('umask 077; : > ' + temporary)
        for index in range((len(payload) + 4095) // 4096):
            encoded = base64.b64encode(payload[index * 4096:(index + 1) * 4096]).decode()
            run(f'printf %s {encoded} | base64 -d | dd of={temporary} bs=4096 seek={index} conv=notrunc 2>/dev/null', retry=True)
        fields = run('sha256sum ' + temporary, retry=True).stdout.split()
        if not fields or fields[0].decode() != report['payload_sha256']:
            raise RuntimeError('temporary payload hash not confirmed; PMSG untouched')
        report['pmsg_write_attempted'] = True
        # Exactly one attempt: a lost response must not duplicate the padding.
        written = run('test -c /dev/pmsg0 && cat ' + temporary + ' > /dev/pmsg0', check=False)
        report['pmsg_write_exit'] = written.returncode
        report['status'] = 'write-returned-success' if written.returncode == 0 else 'write-result-uncertain'
        report['baseline_capture_required'] = True
    except Exception as error:
        report['error'] = str(error)
        if report['pmsg_write_attempted']:
            report['status'] = 'write-result-uncertain'
        raise
    finally:
        try:
            run('rm -f ' + temporary, check=False)
        except Exception:
            report['temporary_cleanup_confirmed'] = False
        (out / 'test.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    print('Capture the baseline before any reboot. Do not repeat this marker write.')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    try:
        stage(args.out)
    except Exception as error:
        raise SystemExit('Stage incomplete: ' + str(error) + '; preserve test.json, do not repeat the write.')
