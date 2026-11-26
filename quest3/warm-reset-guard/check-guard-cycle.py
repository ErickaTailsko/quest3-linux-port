#!/usr/bin/env python3
"""Test default inspection and reversible COLD/WARM/COLD policy, without reboot."""
import argparse
import json
import shlex
import subprocess
import time
from pathlib import Path

GUARD = 'q3_warm_reset_guard'
INFO = 'q3_reset_mode_info'
GUARD_SHA = '1b1e60ac53583e7c70058b839758348756d1a7ac739a993482104f9c17e6c829'
INFO_SHA = 'f155e03cce28479b3eb38546d2b1f9d3c73c16a80e15e1833b79ea3f230f39f3'

def check_cycle(out):
    report = {'status': 'incomplete', 'reboot_requested': False, 'firmware_call_requested': False,
              'policy_override_attempted': False, 'mode_restored_verified': False,
              'checkpoints': [], 'cleanup': {}}
    owned = set()
    def run(command, check=True):
        result = subprocess.run(['adb', 'shell', 'su -c ' + shlex.quote(command)],
                                capture_output=True, timeout=20)
        if check and result.returncode:
            raise RuntimeError('ADB failed: ' + result.stderr.decode(errors='replace')[:300])
        return result
    def present(name):
        value = run(f'if test -d /sys/module/{name}; then printf yes; else printf no; fi').stdout.strip()
        if value not in (b'yes', b'no'):
            raise RuntimeError('module presence check failed')
        return value == b'yes'
    def load(name, arguments=''):
        if present(name):
            raise RuntimeError('module already loaded; not taking ownership: ' + name)
        owned.add(name)  # A lost reply may still mean insertion succeeded.
        result = run(f'insmod /data/local/tmp/{name}.ko {arguments}', check=False)
        if result.returncode:
            raise RuntimeError('insmod failed for ' + name + ': ' + result.stderr.decode(errors='replace')[:300])
    def unload(name):
        if name not in owned:
            return
        for attempt in range(3):
            try:
                if present(name):
                    run('rmmod ' + name, check=False)
                if not present(name):
                    owned.remove(name); report['cleanup'][name] = 'unloaded'; return
            except (RuntimeError, subprocess.TimeoutExpired):
                pass
            if attempt < 2:
                time.sleep(1)
        report['cleanup'][name] = 'not-confirmed'
        raise RuntimeError('unload not confirmed: ' + name)
    def parameter(name, field):
        return int(run(f'cat /sys/module/{name}/parameters/{field}').stdout.strip())
    def independent_snapshot(label):
        load(INFO)
        try:
            mode = parameter(INFO, 'observed_mode')
            panic = parameter(INFO, 'observed_panic_mode')
            report['checkpoints'].append({'phase': label, 'mode': mode, 'panic_mode': panic})
            return mode
        finally:
            unload(INFO)
    # Reserve the local report path before any device mutation.
    with out.open('x') as output:
        try:
            if b'uid=0(' not in run('id').stdout:
                raise RuntimeError('root identity not confirmed')
            if run('getprop sys.boot_completed').stdout.strip() != b'1':
                raise RuntimeError('Android boot completion not confirmed')
            for name, expected in [(GUARD, GUARD_SHA), (INFO, INFO_SHA)]:
                if present(name):
                    raise RuntimeError('pre-existing module must be inspected separately: ' + name)
                fields = run(f'sha256sum /data/local/tmp/{name}.ko').stdout.split()
                if not fields or fields[0].decode() != expected:
                    raise RuntimeError('module hash not confirmed: ' + name)
            if independent_snapshot('before') != 0:
                raise RuntimeError('only the observed COLD default is supported')
            load(GUARD)
            current = parameter(GUARD, 'current_mode'); owner = parameter(GUARD, 'override_owned')
            report['checkpoints'].append({'phase': 'default-inspection', 'mode': current, 'owned': owner})
            if (current, owner) != (0, 0):
                raise RuntimeError('default inspection changed or mismatched policy')
            unload(GUARD)
            report['policy_override_attempted'] = True
            load(GUARD, 'arm=1')
            current = parameter(GUARD, 'current_mode'); owner = parameter(GUARD, 'override_owned')
            report['checkpoints'].append({'phase': 'armed-without-reboot', 'mode': current, 'owned': owner})
            if (current, owner) != (1, 1):
                raise RuntimeError('WARM override not confirmed')
            unload(GUARD)
            if independent_snapshot('after-unload') != 0:
                raise RuntimeError('COLD restoration not verified')
            report.update(status='passed', mode_restored_verified=True)
        except Exception as error:
            report['error'] = str(error)
        finally:
            for name in (GUARD, INFO):
                try:
                    unload(name)
                except Exception as error:
                    report['cleanup'][name] = 'not-confirmed: ' + str(error)
                    report['status'] = 'incomplete'
            json.dump(report, output, indent=2); output.write('\n')
    print(json.dumps(report, indent=2))
    if report['status'] != 'passed':
        print('Do not reboot. If ADB disconnected, reconnect and inspect/unload q3_warm_reset_guard.')
    return report['status'] == 'passed'

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    try:
        raise SystemExit(0 if check_cycle(args.out) else 1)
    except (OSError, ValueError) as error:
        raise SystemExit('Check not started: ' + str(error))
