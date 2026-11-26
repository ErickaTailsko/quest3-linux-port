#!/usr/bin/env python3
"""Capture private Quest 3 memory maps via existing ADB access; fixed read-only commands."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('memory_survey', REPO / 'tools/plan-memory-survey.py')
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)

COMMANDS = {
    'boot-before.txt': 'cat /proc/sys/kernel/random/boot_id',
    'identity.txt': 'id',
    'kernel-release.txt': 'uname -r',
    'page-size.txt': 'getconf PAGESIZE',
    'dt-compatible.bin': 'cat /proc/device-tree/compatible',
    'live.dtb': 'cat /sys/firmware/fdt',
    'iomem.txt': 'cat /proc/iomem',
    'zoneinfo.txt': 'cat /proc/zoneinfo',
    'pagetypeinfo.txt': 'cat /proc/pagetypeinfo',
    'boot-after.txt': 'cat /proc/sys/kernel/random/boot_id',
}
BOOT_ID = re.compile(rb'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
EXPECTED_RELEASE = b'5.10.246-gd7102a837402'


def select_device(adb, serial, runner):
    result = runner([adb, 'devices'], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('ADB device enumeration failed')
    rows = [line.split() for line in result.stdout.decode('utf-8').splitlines()[1:]]
    ready = [row[0] for row in rows if len(row) == 2 and row[1] == 'device']
    if serial is not None:
        if serial not in ready:
            raise ValueError('Selected device is absent, unauthorized or offline')
        return serial
    if len(ready) != 1:
        raise ValueError('Exactly one authorized device is required; use --serial if ambiguous')
    return ready[0]


def validate(data, records, root):
    before, after = data.get('boot-before.txt', b'').strip(), data.get('boot-after.txt', b'').strip()
    boot_ids_valid = bool(BOOT_ID.fullmatch(before) and BOOT_ID.fullmatch(after))
    same_boot = boot_ids_valid and before == after
    errors = []
    if set(records) != set(COMMANDS) or any(record.get('returncode') != 0 or not record.get('bytes') for record in records.values()):
        errors.append('one or more required reads failed, timed out or returned no bytes')
    if not same_boot:
        errors.append('boot identity changed or could not be confirmed')
    if data.get('kernel-release.txt', b'').strip() != EXPECTED_RELEASE:
        errors.append('unexpected kernel release; review ABI and assumptions before proceeding')
    if root and not re.match(rb'uid=0\(', data.get('identity.txt', b'')):
        errors.append('existing su did not confirm root identity')
    if data.get('page-size.txt', b'').strip() != b'4096':
        errors.append('unsupported page size')
    if not re.search(rb'(?m)^Page block order:\s+10\s*$', data.get('pagetypeinfo.txt', b'')):
        errors.append('expected pageblock_order=10 was not confirmed')
    if not re.search(rb'(?m)^Pages per block:\s+1024\s*$', data.get('pagetypeinfo.txt', b'')):
        errors.append('expected 1024 pages per block was not confirmed')
    if not re.search(rb'(?m)^Node\s+\d+, zone\s+\S+', data.get('zoneinfo.txt', b'')):
        errors.append('zoneinfo header missing')
    parsed = False
    try:
        blob = data.get('live.dtb', b'')
        if not 40 <= len(blob) <= 4 * 1024 * 1024:
            raise ValueError('DTB byte count outside supported bounds')
        if struct.unpack_from('>I', blob, 4)[0] != len(blob):
            raise ValueError('DTB total size differs from received byte count')
        nodes, reservations, _ = survey.read(blob)
        if nodes['/'].get('compatible') != data.get('dt-compatible.bin'):
            raise ValueError('DTB and live compatible property differ')
        survey.plan(nodes, reservations, data.get('iomem.txt', b'').decode('utf-8'))
        parsed = True
    except (ValueError, KeyError, UnicodeError, struct.error) as error:
        errors.append('map validation failed: ' + str(error))
    return {'boot_ids_valid': boot_ids_valid, 'same_boot': same_boot,
            'map_geometry_inputs_parse': parsed, 'errors': errors}


def collect(out, adb='adb', serial=None, root=False, runner=subprocess.run):
    # Refuse absent/ambiguous devices before creating an output directory.
    selected = select_device(adb, serial, runner)
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    report = {'status': 'incomplete', 'root_reads': root,
              'device_writes_requested': False, 'module_load_requested': False,
              'cpu_pause_requested': False, 'pages_acquired': False,
              'reboot_requested': False, 'live_metadata_atomic': False,
              'ownership_proven': False, 'dma_safety_proven': False, 'boot_ready': False,
              'note': 'Private raw evidence; review before publishing. No serial or boot UUID '
                      'is copied into this manifest. Boot IDs remain in the raw text files. '
                      'Successful capture does not resolve dynamic reservations or validate PFNs.',
              'records': {}}
    data = {}

    def save():
        (out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')

    save()
    for name, command in COMMANDS.items():
        # ADB joins its remote arguments; quote the entire su command payload.
        remote = 'su -c ' + shlex.quote(command) if root else command
        argv = [adb, '-s', selected, 'exec-out', remote]
        record = {'command': command}
        stdout, stderr = b'', b''
        try:
            result = runner(argv, capture_output=True, timeout=30)
            stdout, stderr = result.stdout, result.stderr
            record['returncode'] = result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b'', error.stderr or b''
            record['error'] = 'timeout; not retried'
        except OSError:
            record['error'] = 'could not launch ADB; not retried'
        with (out / name).open('xb') as stream:
            stream.write(stdout)
        with (out / (name + '.stderr')).open('xb') as stream:
            stream.write(stderr)
        record.update(bytes=len(stdout), sha256=hashlib.sha256(stdout).hexdigest(),
                      stderr_bytes=len(stderr), stderr_sha256=hashlib.sha256(stderr).hexdigest())
        data[name] = stdout
        report['records'][name] = record
        save()
    report['validation'] = validate(data, report['records'], root)
    report['status'] = 'captured-and-validated' if not report['validation']['errors'] else 'rejected'
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', help='Select an already authorized device; not recorded in manifest')
    parser.add_argument('--root', action='store_true', help='Read via existing su; never invokes adb root or installs root')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    parser.add_argument('--out', type=Path, default=REPO / 'private-diagnostics' / ('memory-maps-' + stamp),
                        help='New private evidence directory; existing output is never overwritten')
    args = parser.parse_args()
    try:
        report = collect(args.out, args.adb, args.serial, args.root)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        # Do not print raw ADB responses, device serials or boot UUIDs.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        parser.exit(2, message + '; no device write requested\n')
    print(f"{report['status']}: {args.out}; no device write, module load or CPU pause requested")
    return 0 if report['status'] == 'captured-and-validated' else 2


if __name__ == '__main__':
    raise SystemExit(main())
