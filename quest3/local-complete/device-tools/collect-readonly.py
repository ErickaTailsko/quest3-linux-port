#!/usr/bin/env python3
"""Collect Quest kernel diagnostics; never load modules or change the device."""
import argparse, datetime, gzip, hashlib, json, shlex, subprocess
from pathlib import Path

COMMANDS = {
    'kernel-version.txt': 'cat /proc/version',
    'kernel-release.txt': 'uname -r',
    'device-config.gz': 'cat /proc/config.gz',
    'dt-compatible.bin': 'cat /proc/device-tree/compatible',
    'live-device-tree.dtb': 'cat /sys/firmware/fdt',
    'core-hang-property-paths.txt': 'find /sys/firmware/devicetree/base -name qcom,chd-percpu-info -print',
    'core-hang-properties-hex.txt': 'find /sys/firmware/devicetree/base -name qcom,chd-percpu-info -exec od -An -tx1 {} \\;',
    'syncboss-driver.txt': 'readlink /sys/bus/spi/devices/spi0.0/driver',
    'usb-driver.txt': 'readlink /sys/bus/platform/devices/a600000.dwc3/driver',
    'gpu-driver.txt': 'readlink /sys/bus/platform/devices/3d00000.qcom,kgsl-3d0/driver',
    'watchdog-driver.txt': 'readlink /sys/bus/platform/devices/hypervisor:qcom,gh-watchdog/driver',
    'watchdog-disabled.txt': 'cat /sys/bus/platform/devices/hypervisor:qcom,gh-watchdog/disable',
    'kernel-log.txt': 'dmesg',
    'pstore-list.txt': 'ls -l /sys/fs/pstore',
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', help='Required when more than one device is connected')
    parser.add_argument('--root', action='store_true', help='Use existing su for read commands; does not run adb root')
    parser.add_argument('--out', type=Path, default=Path('quest3-diagnostics-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')))
    args = parser.parse_args()
    result = subprocess.run([args.adb, 'devices'], capture_output=True, timeout=30, check=True)
    devices = [line.split() for line in result.stdout.decode().splitlines()[1:] if line.strip()]
    ready = [fields[0] for fields in devices if len(fields) == 2 and fields[1] == 'device']
    if args.serial:
        if args.serial not in ready:
            parser.error('Selected device is absent, unauthorized or offline')
        serial = args.serial
    elif len(ready) == 1:
        serial = ready[0]
    else:
        parser.error('Select exactly one authorized device with --serial')
    args.out.mkdir(parents=True, exist_ok=False)
    records = {}
    for name, command in COMMANDS.items():
        argv = [args.adb, '-s', serial, 'exec-out']
        argv += ['su', '-c', shlex.quote(command)] if args.root else [command]
        try:
            result = subprocess.run(argv, capture_output=True, timeout=30)
            (args.out/name).write_bytes(result.stdout)
            (args.out/(name+'.stderr')).write_bytes(result.stderr)
            records[name] = {'command': command, 'returncode': result.returncode,
                             'sha256': hashlib.sha256(result.stdout).hexdigest()}
        except subprocess.TimeoutExpired:
            records[name] = {'command': command, 'error': 'timeout'}
    config = args.out/'device-config.gz'
    if records.get(config.name, {}).get('returncode') == 0:
        try:
            (args.out/'device-config.txt').write_bytes(gzip.decompress(config.read_bytes()))
        except (OSError, EOFError) as error:
            records[config.name]['decode_error'] = str(error)
    (args.out/'manifest.json').write_text(json.dumps({'serial': serial, 'root_reads': args.root,
        'device_modified': False, 'records': records}, indent=2)+'\n')
    failures = sum(x.get('returncode') != 0 or 'decode_error' in x for x in records.values())
    print(f'Collected in {args.out}; unavailable/failed reads: {failures}. No modules loaded or device settings changed.')
    return 2 if failures else 0

if __name__ == '__main__':
    raise SystemExit(main())
