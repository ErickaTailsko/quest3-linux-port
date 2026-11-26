#!/usr/bin/env python3
"""One explicitly consented stop_machine sample; no reboot or page acquisition."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

EXPECTED = 'ee4692aada2c6b6b5fc562f84b2c1d9210d5b0fdb69aa83577c47b6a9cddbbc5'
NAME = 'q3_pageblock_snapshot'
REMOTE_REPORT = '/sys/kernel/' + NAME + '/report'


def validate_report(text):
    lines = text.strip().splitlines()
    header = re.fullmatch(r'heads_only=1 count=13 callback_ns=(\d+) all_pfns_checked=0 owned=0 dma_safe=0', lines[0] if lines else '')
    if not header or len(lines) != 14 or int(header[1]) > 1000000:
        raise ValueError('invalid or incomplete sample header')
    blocks = []
    names = ['UNMOVABLE', 'MOVABLE', 'RECLAIMABLE', 'CMA', 'HIGHATOMIC', 'ISOLATE']
    for index, line in enumerate(lines[1:]):
        match = re.fullmatch(r'block=0x([0-9a-f]+) zone=([A-Za-z0-9_]+) migratetype=([0-5]) head_reserved=([01])', line)
        if not match or int(match[1], 16) != 0x90000000 + index * 0x400000:
            raise ValueError('unexpected pageblock address/metadata')
        blocks.append({'physical_base': '0x' + match[1], 'zone': match[2],
                       'migratetype': names[int(match[3])], 'head_reserved': match[4] == '1'})
    return {'callback_ns': int(header[1]), 'blocks': blocks, 'all_pfns_checked': False,
            'allocator_ownership_acquired': False, 'dma_quiescence_proven': False}


def collect(out, module, serial):
    if hashlib.sha256(module.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('reviewed module hash differs; nothing sent')
    out.mkdir(parents=True, exist_ok=False)
    prefix = ['adb', '-s', serial]
    remote = '/data/local/tmp/eris-pageblock-' + uuid.uuid4().hex + '.ko'
    report = {'status': 'incomplete', 'reboot_requested': False, 'page_acquisition_requested': False,
              'insertion_attempts': 0, 'cleanup_confirmed': False, 'events': []}
    boot = None
    uploaded = False

    def read(command):
        result = subprocess.run(prefix + ['exec-out', 'su', '-c', command], capture_output=True, timeout=30)
        report['events'].append({'command': command, 'returncode': result.returncode,
                                 'stdout': result.stdout.decode(errors='replace'),
                                 'stderr': result.stderr.decode(errors='replace')})
        if result.returncode:
            raise RuntimeError('command failed: ' + command)
        return result.stdout

    def save():
        (out / 'operation.json').write_text(json.dumps(report, indent=2) + '\n')

    try:
        if b'uid=0(' not in read('id'):
            raise ValueError('root identity not confirmed')
        if read('uname -r').strip() != b'5.10.246-gd7102a837402':
            raise ValueError('unexpected running kernel')
        boot = read('cat /proc/sys/kernel/random/boot_id').strip()
        if not re.fullmatch(rb'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot):
            raise ValueError('invalid boot identity')
        report['boot_id_before'] = boot.decode()
        report['cpus_before'] = read('cat /sys/devices/system/cpu/online').strip().decode()
        if any(line.split()[0] == NAME.encode() for line in read('cat /proc/modules').splitlines()):
            raise ValueError('module already present; no ownership assumed')
        read('test ! -e /sys/kernel/' + NAME)
        uploaded = True
        subprocess.run(prefix + ['push', str(module), remote], check=True, timeout=45)
        if read('sha256sum ' + remote).split()[0].decode() != EXPECTED:
            raise ValueError('remote module hash differs')
        if read('cat /proc/sys/kernel/random/boot_id').strip() != boot:
            raise ValueError('boot changed before insertion')
        report['insertion_attempts'] = 1
        save()  # Preserve intent before the one potentially uncertain operation.
        read('insmod ' + remote + ' sample=1')  # Never retry this operation.
        data = read('cat ' + REMOTE_REPORT)
        with (out / 'sample.txt').open('xb') as stream:
            stream.write(data)
        report['sample'] = validate_report(data.decode('ascii'))
        report['sample_sha256'] = hashlib.sha256(data).hexdigest()
        if read('cat /proc/sys/kernel/random/boot_id').strip() != boot:
            raise ValueError('boot changed during sample')
        report['status'] = 'sample-verified'
    except Exception as error:
        report['error'] = repr(error)
    finally:
        try:
            current = read('cat /proc/sys/kernel/random/boot_id').strip()
            report['boot_id_after'] = current.decode()
            if current != boot:
                raise RuntimeError('boot identity changed/unconfirmed; no unowned cleanup')
            if report['insertion_attempts']:
                modules = read('cat /proc/modules').splitlines()
                if any(line.split()[0] == NAME.encode() for line in modules):
                    read('rmmod ' + NAME)
                modules = read('cat /proc/modules').splitlines()
                if any(line.split()[0] == NAME.encode() for line in modules):
                    raise RuntimeError('module remains present')
                read('test ! -e /sys/kernel/' + NAME)
                report['cleanup_confirmed'] = True
            if uploaded:
                read('rm -f ' + remote)
                read('test ! -e ' + remote)
            report['cpus_after'] = read('cat /sys/devices/system/cpu/online').strip().decode()
            if report.get('cpus_before') != report['cpus_after']:
                raise RuntimeError('online CPU mask changed')
        except Exception as error:
            report['cleanup_error'] = repr(error)
        save()
    if report['status'] != 'sample-verified' or not report['cleanup_confirmed'] or 'cleanup_error' in report:
        raise RuntimeError('sample/cleanup not fully verified; preserve operation.json, do not repeat')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--ack-system-pause', action='store_true', help='Explicit consent to system pause/lockup risk')
    args = parser.parse_args()
    if not args.ack_system_pause:
        parser.error('--ack-system-pause is required; nothing executed')
    try:
        report = collect(args.out, args.module, args.serial)
    except Exception as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'events'}, indent=2))
