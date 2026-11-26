#!/usr/bin/env python3
"""Run the production cycle controller against failure-injected ADB stubs."""
from pathlib import Path
import importlib.util
import json
import re
import shlex
import subprocess
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cycle', root / 'check-guard-cycle.py')
cycle = importlib.util.module_from_spec(spec); spec.loader.exec_module(cycle)
for scenario in ['valid', 'hash-mismatch', 'preexisting', 'booting', 'lost-arm-reply', 'read-after-arm-fails', 'unload-fails', 'foreign-mode']:
    state = {'mode': 0, 'modules': {}, 'commands': [], 'faulted': False}
    if scenario == 'preexisting': state['modules'][cycle.GUARD] = {'owned': False}
    def adb(argv, **kwargs):
        command = shlex.split(argv[-1])[2]; state['commands'].append(command)
        code = 0; out = b''
        if command == 'id': out = b'uid=0(root)'
        elif command == 'getprop sys.boot_completed': out = b'0' if scenario == 'booting' else b'1'
        elif command.startswith('if test -d '):
            name = command.split()[3].rsplit('/', 1)[-1].rstrip(';')
            out = b'yes' if name in state['modules'] else b'no'
        elif command.startswith('sha256sum '):
            expected = cycle.GUARD_SHA if cycle.GUARD in command else cycle.INFO_SHA
            out = (expected if scenario != 'hash-mismatch' else '0' * 64).encode()
        elif command.startswith('insmod '):
            name = command.split()[1].rsplit('/', 1)[-1][:-3]
            assert name not in state['modules']
            if name == cycle.INFO:
                state['modules'][name] = {'snapshot': state['mode']}
            elif 'arm=1' in command:
                assert state['mode'] == 0
                state['mode'] = 1; state['modules'][name] = {'owned': True}
                if scenario == 'lost-arm-reply': raise subprocess.TimeoutExpired(argv, 20)
            else: state['modules'][name] = {'owned': False}
        elif command.startswith('rmmod '):
            name = command.split()[1]
            value = state['modules'][name]
            if name == cycle.GUARD and value['owned']:
                if scenario == 'unload-fails': return subprocess.CompletedProcess(argv, 1, b'', b'busy')
                if scenario == 'foreign-mode': state['mode'] = 2
                if state['mode'] == 1: state['mode'] = 0
            del state['modules'][name]
        elif command.startswith('cat /sys/module/'):
            _, _, _, name, _, field = command.split()[1].split('/')
            value = state['modules'][name]
            if field == 'current_mode':
                if scenario == 'read-after-arm-fails' and value['owned'] and not state['faulted']:
                    state['faulted'] = True;return subprocess.CompletedProcess(argv, 1, b'', b'closed')
                out = str(state['mode']).encode()
            elif field == 'override_owned': out = str(int(value['owned'])).encode()
            elif field == 'observed_mode': out = str(value['snapshot']).encode()
            elif field == 'observed_panic_mode': out = b'-1'
            else: raise AssertionError(field)
        else: raise AssertionError(command)
        return subprocess.CompletedProcess(argv, code, out, b'')
    with tempfile.TemporaryDirectory() as temp:
        report = Path(temp) / 'result.json'
        with patch.object(cycle.subprocess, 'run', side_effect=adb), patch.object(cycle.time, 'sleep'), patch('builtins.print'):
            passed = cycle.check_cycle(report)
        data = json.loads(report.read_text())
        assert passed == (scenario == 'valid'), (scenario, data)
        assert not data['reboot_requested'] and not data['firmware_call_requested']
        if scenario == 'valid':
            assert data['mode_restored_verified'] and state['mode'] == 0 and not state['modules']
            assert [entry['mode'] for entry in data['checkpoints']] == [0, 0, 1, 0]
        elif scenario == 'unload-fails':
            assert state['mode'] == 1 and cycle.GUARD in state['modules']
            assert 'not-confirmed' in data['cleanup'][cycle.GUARD]
        elif scenario == 'preexisting':
            assert cycle.GUARD in state['modules']
            assert not any(command.startswith('rmmod ') for command in state['commands'])
        elif scenario == 'foreign-mode': assert state['mode'] == 2 and not state['modules']
        else: assert state['mode'] == 0 and not state['modules']
        assert not any(re.search(r'\b(reboot|setprop)\b', command) for command in state['commands'])
print('PASS actual cycle: COLD/WARM/COLD, independent restoration read, foreign/preexisting state, boot/hash gates, lost reply, read failure and uncertain cleanup')
