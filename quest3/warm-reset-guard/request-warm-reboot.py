#!/usr/bin/env python3
"""Validate a fresh PMSG baseline; request one guarded reboot only with --reboot-now.
Never retries a reboot request and never unloads the policy after commit starts.
"""
import argparse
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

NAME = 'q3_warm_reset_guard'
SHA = '1b1e60ac53583e7c70058b839758348756d1a7ac739a993482104f9c17e6c829'

def baseline_check(tools, test, dtb):
    if str(tools.resolve()) not in sys.path:
        sys.path.insert(0, str(tools.resolve()))
    path = tools / 'check-pmsg-baseline.py'
    spec = importlib.util.spec_from_file_location('baseline_checker', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.check(test, test / 'before', dtb)

def request(tools, test, dtb, cycle, reboot_now=False):
    baseline = baseline_check(tools, test, dtb)
    if not baseline.get('baseline_marker_verified'):
        raise ValueError('fresh marker baseline not verified')
    previous = json.loads(cycle.read_text())
    if previous.get('status') != 'passed' or not previous.get('mode_restored_verified'):
        raise ValueError('reversible policy cycle not verified')
    def run(command, check=True):
        result = subprocess.run(['adb', 'shell', 'su -c ' + shlex.quote(command)],
                                capture_output=True, timeout=20)
        if check and result.returncode:
            raise RuntimeError('ADB command failed: ' + result.stderr.decode(errors='replace')[:300])
        return result
    def present():
        data = run(f'if test -d /sys/module/{NAME}; then printf yes; else printf no; fi').stdout.strip()
        if data not in (b'yes', b'no'):
            raise RuntimeError('module presence not confirmed')
        return data == b'yes'
    if b'uid=0(' not in run('id').stdout:
        raise RuntimeError('root identity not confirmed')
    if run('getprop sys.boot_completed').stdout.strip() != b'1':
        raise RuntimeError('Android startup not complete')
    boot = run('cat /proc/sys/kernel/random/boot_id').stdout.strip().decode()
    if boot != baseline['boot_id']:
        raise ValueError('baseline belongs to another kernel boot')
    if present():
        raise ValueError('guard already loaded; inspect/unload separately')
    fields = run(f'sha256sum /data/local/tmp/{NAME}.ko').stdout.split()
    if not fields or fields[0].decode() != SHA:
        raise ValueError('guard module hash not confirmed')
    report = {'status': 'preflight-passed', 'boot_id_before': boot,
              'baseline_snapshot_sha256': baseline['snapshot_sha256'],
              'marker': baseline['marker'], 'reboot_requested': False,
              'warm_firmware_path_observed': False, 'retention_validated': False,
              'policy_override_attempted': False, 'commit_started': False}
    if not reboot_now:
        return report
    # Exclusive creation prohibits an accidental second request for this test.
    with (test / 'warm-request.json').open('x') as output:
        def save():
            output.seek(0); json.dump(report, output, indent=2); output.write('\n')
            output.truncate(); output.flush(); os.fsync(output.fileno())
        possible_owner = False
        try:
            report['policy_override_attempted'] = True
            save()
            possible_owner = True
            run(f'insmod /data/local/tmp/{NAME}.ko arm=1')
            mode = int(run(f'cat /sys/module/{NAME}/parameters/current_mode').stdout.strip())
            owner = int(run(f'cat /sys/module/{NAME}/parameters/override_owned').stdout.strip())
            report.update(mode_before_request=mode, guard_owned_before_request=owner)
            if (mode, owner) != (1, 1):
                raise RuntimeError('WARM policy and guard ownership not confirmed')
            # Persist provenance BEFORE the irreversible request. From here a
            # failed/lost ADB reply cannot be treated as a cancelled reboot.
            report.update(status='request-starting', commit_started=True, reboot_requested=True)
            save()
            result = subprocess.run(['adb', 'reboot'], capture_output=True, timeout=20)
            report.update(reboot_requested=True, adb_reboot_exit=result.returncode,
                          adb_reboot_acknowledged=result.returncode == 0,
                          status='request-sent' if result.returncode == 0 else 'request-uncertain')
        except Exception as error:
            report['error'] = str(error)
            report['status'] = 'request-uncertain' if report['commit_started'] else 'aborted-before-request'
        finally:
            if possible_owner and not report['commit_started']:
                report['rollback_unload_confirmed'] = False
                for attempt in range(3):
                    try:
                        if present(): run('rmmod ' + NAME, check=False)
                        if not present():
                            report['rollback_unload_confirmed'] = True; break
                    except Exception:
                        pass
                    if attempt < 2: time.sleep(1)
            # Do not revert mode during an in-progress device_shutdown().
            # Never issue a second reset to find out what happened.
            save()
    return report

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tools', type=Path, default=Path.home() / 'quest3-ramoops-readonly')
    ap.add_argument('--test', type=Path, required=True)
    ap.add_argument('--dtb', type=Path, required=True)
    ap.add_argument('--cycle', type=Path, default=Path.home() / 'quest3-warm-guard-cycle.json')
    ap.add_argument('--reboot-now', action='store_true', help='actually arm WARM and request one ordinary adb reboot')
    args = ap.parse_args()
    try:
        result = request(args.tools, args.test, args.dtb, args.cycle, args.reboot_now)
        print(json.dumps(result, indent=2))
        if result['status'] not in ('preflight-passed', 'request-sent'):
            raise SystemExit('Stop. Preserve warm-request.json; do not repeat a reset request.')
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit('Stopped: ' + str(error))
