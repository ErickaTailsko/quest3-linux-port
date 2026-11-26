#!/usr/bin/env python3
"""Mock ADB lifecycle; no real device or system pause."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('controller', Path(__file__).with_name('collect-once.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
boot = b'12345678-1234-1234-1234-123456789abc\n'
sample = 'heads_only=1 count=13 callback_ns=20000 all_pfns_checked=0 owned=0 dma_safe=0\n'
sample += ''.join(f'block=0x{0x90000000+i*0x400000:x} zone=DMA migratetype=1 head_reserved=0\n' for i in range(13))
assert len(module.validate_report(sample)['blocks']) == 13
for bad in [sample.replace('count=13', 'count=12'), sample.replace('callback_ns=20000', 'callback_ns=2000000'),
            sample.replace('block=0x90000000', 'block=0x80000000'), sample.replace('migratetype=1', 'migratetype=9'),
            '\n'.join(sample.splitlines()[:-1])]:
    try:
        module.validate_report(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid report accepted')

with tempfile.TemporaryDirectory(prefix='q3-sample-controller-') as temporary:
    root = Path(temporary)
    ko = root / 'module.ko'
    ko.write_bytes(b'fake module for lifecycle model')
    module.EXPECTED = hashlib.sha256(ko.read_bytes()).hexdigest()
    for mode in ['success', 'lost-insertion-response', 'bad-report', 'preexisting', 'cleanup-failure']:
        loaded = [mode == 'preexisting']
        calls = []
        def adb(argv, **kwargs):
            assert argv[:3] == ['adb', '-s', 'TEST'], argv
            calls.append(argv)
            data = b''
            if argv[3] == 'push':
                pass
            else:
                assert argv[3:6] == ['exec-out', 'su', '-c']
                command = argv[6]
                if command == 'id': data = b'uid=0(root)\n'
                elif command == 'uname -r': data = b'5.10.246-gd7102a837402\n'
                elif command == 'cat /proc/sys/kernel/random/boot_id': data = boot
                elif command == 'cat /sys/devices/system/cpu/online': data = b'0-5\n'
                elif command == 'cat /proc/modules': data = b'q3_pageblock_snapshot 4096 0 - Live 0x0\n' if loaded[0] else b''
                elif command.startswith('sha256sum '): data = (module.EXPECTED + '  module\n').encode()
                elif command.startswith('insmod '):
                    loaded[0] = True
                    if mode == 'lost-insertion-response':
                        raise subprocess.TimeoutExpired(argv, 30)
                elif command == 'cat ' + module.REMOTE_REPORT:
                    data = (sample if mode != 'bad-report' else 'bad sample').encode()
                elif command == 'rmmod ' + module.NAME:
                    if mode == 'cleanup-failure':
                        return subprocess.CompletedProcess(argv, 1, b'', b'busy')
                    loaded[0] = False
                elif command.startswith(('test ! -e ', 'rm -f ')):
                    pass
                else: raise AssertionError(command)
            return subprocess.CompletedProcess(argv, 0, data, b'')
        out = root / mode
        with patch.object(module.subprocess, 'run', side_effect=adb):
            if mode == 'success':
                report = module.collect(out, ko, 'TEST')
                assert report['cleanup_confirmed'] and not loaded[0]
            else:
                try: module.collect(out, ko, 'TEST')
                except RuntimeError: pass
                else: raise AssertionError('invalid lifecycle accepted')
        report = json.loads((out / 'operation.json').read_text())
        inserts = [call for call in calls if call[-1].startswith('insmod ')]
        assert len(inserts) == (0 if mode == 'preexisting' else 1)
        if mode == 'preexisting': assert loaded[0] and not any('rmmod ' in call[-1] for call in calls)
        if mode in ['lost-insertion-response', 'bad-report']: assert not loaded[0]
        if mode == 'cleanup-failure': assert 'cleanup_error' in report
        assert not report['reboot_requested'] and not report['page_acquisition_requested']
print('PASS sample controller: exact-once insertion, lost response cleanup, preexisting ownership, invalid data and cleanup failure; fake ADB only')
