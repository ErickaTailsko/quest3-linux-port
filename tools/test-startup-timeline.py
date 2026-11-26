#!/usr/bin/env python3
"""Offline tests; no ADB or device access."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('timeline', Path(__file__).with_name('analyze-startup-timeline.py'))
timeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timeline)
stat = '8578 (magiskd) ' + ' '.join(['S'] + ['0'] * 18 + ['6949'] + ['0'] * 10)
kernel = "\x1b[32m[   80.461494] \x1b[0minit: starting service 'panicreporter'...\n"
kernel += "[   80.575310] init: Service 'panicreporter' (pid 10240) exited with status 0\n"
events = '    15.130  1567 1639 I boot_progress_enable_screen: 15130\n'
events += '    80.365  9382 9416 I boot_progress_enable_screen: 80365\n'
result = timeline.analyze(kernel, events, stat, 100)
assert result['magisk_process_start_seconds'] == 69.49
assert result['screen_enable_seconds'] == [15.130, 80.365]
assert result['observed_panicreporter_starts_after_magisk'] == [80.461494]
assert result['panicreporter_exit_seconds'] == [80.575310]
assert not result['capture_before_all_pstore_consumers_validated']
assert not result['kernel_reset_count_inferred']
assert not result['root_command_availability_at_process_start_proven']
earlier = "[   16.0] init: starting service 'panicreporter'...\n" + kernel
assert timeline.analyze(earlier, events, stat, 100)['observed_panicreporter_starts_before_or_at_magisk'] == [16.0]
missing = timeline.analyze('', '', stat, 100)
assert missing['kernel_log_first_observed_seconds'] is None
assert missing['panicreporter_start_seconds'] == []
for invalid_stat, ticks in [(stat, 0), (stat, -1), (stat, float('nan')),
                            (stat, float('inf')), ('bad record', 100),
                            ('1 (magiskd) S 0', 100), (stat.replace('magiskd', 'init'), 100)]:
    try:
        timeline.analyze(kernel, events, invalid_stat, ticks)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid process metadata accepted')
print('PASS startup evidence: time units, ANSI, repeated framework events, earlier consumer, missing logs and invalid metadata; no early-root/reset inference')
