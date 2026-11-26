#!/usr/bin/env python3
"""Test actual one-shot reset controller without issuing any real ADB command."""
import importlib.util
import json
import shlex
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('request', root / 'request-warm-reboot.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
boot = '12345678-1234-1234-1234-123456789abc'
baseline = {'baseline_marker_verified': True, 'boot_id': boot,
            'snapshot_sha256': 'a' * 64, 'marker': 'Q3_RAW_RETENTION_' + '1' * 32}
for scenario in ['check-only', 'commit', 'reset-reply-lost', 'reset-rejected', 'arm-reply-lost',
                 'read-failed', 'preexisting', 'different-boot', 'wrong-hash', 'existing-request']:
    state = {'loaded': scenario == 'preexisting', 'mode': 0, 'requests': 0, 'unloads': 0}
    def adb(argv, **kwargs):
        if argv == ['adb', 'reboot']:
            state['requests'] += 1
            assert state['loaded'] and state['mode'] == 1
            if scenario == 'reset-reply-lost': raise subprocess.TimeoutExpired(argv, 20)
            return subprocess.CompletedProcess(argv, 1 if scenario == 'reset-rejected' else 0, b'', b'')
        command = shlex.split(argv[-1])[2]; out = b''
        if command == 'id': out = b'uid=0(root)'
        elif command.startswith('getprop '): out = b'1'
        elif 'boot_id' in command: out = (boot if scenario != 'different-boot' else 'b' * 36).encode()
        elif command.startswith('if test -d '): out = b'yes' if state['loaded'] else b'no'
        elif command.startswith('sha256sum '): out = (module.SHA if scenario != 'wrong-hash' else '0' * 64).encode()
        elif command.startswith('insmod '):
            state.update(loaded=True, mode=1)
            if scenario == 'arm-reply-lost': raise subprocess.TimeoutExpired(argv, 20)
        elif command.startswith('cat /sys/module/'):
            if scenario == 'read-failed': return subprocess.CompletedProcess(argv, 1, b'', b'closed')
            out = b'1'
        elif command.startswith('rmmod '): state.update(loaded=False, mode=0, unloads=state['unloads'] + 1)
        else: raise AssertionError(command)
        return subprocess.CompletedProcess(argv, 0, out, b'')
    with tempfile.TemporaryDirectory() as temp:
        test = Path(temp); cycle = test / 'cycle.json'
        cycle.write_text(json.dumps({'status': 'passed', 'mode_restored_verified': True}))
        if scenario == 'existing-request': (test / 'warm-request.json').write_text('previous request')
        with patch.object(module, 'baseline_check', return_value=baseline), patch.object(module.subprocess, 'run', side_effect=adb), patch.object(module.time, 'sleep'):
            if scenario in ['preexisting', 'different-boot', 'wrong-hash', 'existing-request']:
                try: module.request(test, test, test, cycle, True)
                except (ValueError, FileExistsError): pass
                else: raise AssertionError('invalid preflight accepted: ' + scenario)
                assert state['requests'] == 0 and state['unloads'] == 0
                continue
            result = module.request(test, test, test, cycle, scenario != 'check-only')
            if scenario == 'check-only':
                assert result['status'] == 'preflight-passed' and not state['loaded']
                assert not (test / 'warm-request.json').exists()
            elif scenario in ['commit', 'reset-reply-lost', 'reset-rejected']:
                assert state['requests'] == 1 and state['unloads'] == 0
                assert state['loaded'] and state['mode'] == 1
                assert result['commit_started'] and result['reboot_requested']
                assert result['status'] == ('request-sent' if scenario == 'commit' else 'request-uncertain')
                saved = json.loads((test / 'warm-request.json').read_text())
                assert saved['status'] == result['status']
            else:
                assert state['requests'] == 0 and state['unloads'] == 1
                assert not state['loaded'] and state['mode'] == 0
                assert result['status'] == 'aborted-before-request'
                assert result['rollback_unload_confirmed'] and not result['reboot_requested']
print('PASS actual reset controller: read-only preflight, one request only, no mode reversal after commit, lost/rejected replies, precommit rollback and duplicate-request refusal')
