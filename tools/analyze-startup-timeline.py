#!/usr/bin/env python3
"""Summarize captured startup evidence offline; never infer unobserved boots."""
import argparse
import json
import math
import re
from pathlib import Path


def analyze(kernel_log, events_log, process_stat, clock_ticks):
    if not math.isfinite(clock_ticks) or clock_ticks <= 0:
        raise ValueError('clock ticks must be positive and finite')
    # /proc/PID/stat comm can contain spaces or parentheses.
    match = re.fullmatch(r'\d+ \((.*)\) (\S+ .+)', process_stat.strip())
    if not match or match[1] != 'magiskd':
        raise ValueError('expected one magiskd /proc/PID/stat record')
    fields = match[2].split()  # Starts at field 3 (state).
    if len(fields) < 20:
        raise ValueError('truncated process stat')
    start_ticks = int(fields[19])  # Field 22: starttime.
    if start_ticks < 0:
        raise ValueError('negative process start time')
    root_start = start_ticks / clock_ticks
    clean = re.sub(r'\x1b\[[0-9;]*m', '', kernel_log)
    timestamps = []
    starts = []
    exits = []
    for line in clean.splitlines():
        stamp = re.match(r'^\[\s*(\d+(?:\.\d+)?)\]', line)
        if not stamp:
            continue
        timestamp = float(stamp[1])
        timestamps.append(timestamp)
        if re.search(r"\binit: starting service 'panicreporter'\.\.\.", line):
            starts.append(timestamp)
        if re.search(r"\binit: Service 'panicreporter' .* exited with status", line):
            exits.append(timestamp)
    screens = []
    for line in events_log.splitlines():
        stamp = re.match(r'^\s*(\d+(?:\.\d+)?)\s+.*\bboot_progress_enable_screen:', line)
        if stamp:
            screens.append(float(stamp[1]))
    return {
        'scope': 'offline observed timestamps only',
        'magisk_process_start_seconds': root_start,
        'root_command_availability_at_process_start_proven': False,
        'kernel_log_first_observed_seconds': min(timestamps) if timestamps else None,
        'kernel_log_last_observed_seconds': max(timestamps) if timestamps else None,
        'screen_enable_seconds': screens,
        'panicreporter_start_seconds': starts,
        'panicreporter_exit_seconds': exits,
        'observed_panicreporter_starts_after_magisk': [t for t in starts if t > root_start],
        'observed_panicreporter_starts_before_or_at_magisk': [t for t in starts if t <= root_start],
        'capture_before_all_pstore_consumers_validated': False,
        'kernel_reset_count_inferred': False,
        'note': 'A process start is not proof that su or a hook was ready. Missing events '
                'are not proof of non-execution. Repeated framework events do not prove '
                'kernel resets. Other pstore consumers and initial log coverage remain unvalidated.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-log', type=Path, required=True)
    parser.add_argument('--events-log', type=Path, required=True,
                        help='logcat events captured with -v monotonic')
    parser.add_argument('--magisk-stat', type=Path, required=True,
                        help='file whose first line is the magiskd proc stat record')
    parser.add_argument('--clock-ticks', type=float, required=True,
                        help='CLK_TCK measured on the device, not the host')
    args = parser.parse_args()
    try:
        result = analyze(args.kernel_log.read_text(errors='replace'),
                         args.events_log.read_text(errors='replace'),
                         args.magisk_stat.read_text().splitlines()[0], args.clock_ticks)
    except (ValueError, OSError, IndexError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(result, indent=2))
