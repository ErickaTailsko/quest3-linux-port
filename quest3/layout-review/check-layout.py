#!/usr/bin/env python3
"""Offline placement check. Does not reserve RAM, stage files or execute a boot."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from fdtcheck import read, rewrite

LO, HI, INITRD, DTB = 0x90000000, 0x93400000, 0x93000000, 0x93200000

def check_ram(text):
    ranges = []
    for line in text.splitlines():
        m = re.fullmatch(r'\s*([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+:\s+(.+)', line)
        if m:
            lo, hi = int(m[1], 16), int(m[2], 16) + 1
            if hi <= lo:
                raise ValueError('invalid iomem interval')
            ranges.append((lo, hi, m[3]))
    if not any(lo <= LO and HI <= hi and name == 'System RAM' for lo, hi, name in ranges):
        raise ValueError('window not covered by one visible System RAM extent')
    for lo, hi, name in ranges:
        if name != 'System RAM' and lo < HI and LO < hi:
            raise ValueError('window overlaps iomem resource: ' + name)

def layout(image, initramfs, dtb, iomem):
    check_ram(iomem)
    if len(image) < 64 or image[56:60] != b'ARM\x64':
        raise ValueError('not a raw ARM64 Image')
    offset, size, flags = struct.unpack_from('<QQQ', image, 8)
    if (offset not in (0, 0x80000) or size < len(image) or
        size > INITRD - LO - offset or flags & 1 or not flags & 8 or flags & 6 not in (0, 2)):
        raise ValueError('unsupported Image layout or architecture flags')
    if not 0 < len(initramfs) <= DTB - INITRD or not 40 <= len(dtb) <= HI - DTB:
        raise ValueError('initramfs/DTB size exceeds layout')
    if struct.unpack_from('>I', dtb, 4)[0] != len(dtb):
        raise ValueError('DTB total size differs from file size')
    nodes, reservations, cpu = read(dtb)
    compat = nodes['/'].get('compatible', b'').split(b'\0')
    if b'qcom,anorak' not in compat or b'oculus,eureka' not in compat:
        raise ValueError('not the supported Quest 3 board')
    reserved = nodes.get('/reserved-memory', {})
    if reserved.get('#address-cells') != struct.pack('>I', 2) or reserved.get('#size-cells') != struct.pack('>I', 2) or reserved.get('ranges') != b'':
        raise ValueError('unsupported reserved-memory addressing')
    for path, props in nodes.items():
        if path.startswith('/reserved-memory/'):
            reg = props.get('reg', b'')
            if len(reg) % 16:
                raise ValueError('invalid reservation reg: ' + path)
            reservations += list(struct.iter_unpack('>QQ', reg))
    for address, length in reservations:
        if address + length > 1 << 64 or (length and address < HI and LO < address + length):
            raise ValueError('DT reservation overlaps window or overflows')
    chosen = nodes.get('/chosen', {})
    expected = {'linux,initrd-start': INITRD, 'linux,initrd-end': INITRD + len(initramfs)}
    matches = all(chosen.get(name) == struct.pack('>Q', value) for name, value in expected.items())
    return dict(window_start=hex(LO), window_end_exclusive=hex(HI),
                image_entry=hex(LO + offset), image_size=hex(size),
                image_end_page_aligned=hex(LO + offset + ((size + 4095) & ~4095)),
                initrd_start=hex(INITRD), initrd_end=hex(INITRD + len(initramfs)),
                dtb_address=hex(DTB), dtb_end=hex(DTB + len(dtb)),
                captured_iomem_and_dt_overlap_check=True,
                chosen_initrd_matches=matches,
                dt_dynamic_reservations_require_matching_iomem=True,
                destination_ram_reserved_by_this_check=False,
                bootargs_reviewed=False,
                boot_ready=False, boot_tested=False)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'initramfs', 'dtb', 'iomem'):
        ap.add_argument('--' + name, required=True, type=Path)
    ap.add_argument('--out-dtb', type=Path, help='new copy with only the two chosen initrd addresses corrected')
    args = ap.parse_args()
    files = {name: getattr(args, name).read_bytes() for name in ('image', 'initramfs', 'dtb', 'iomem')}
    report = layout(files['image'], files['initramfs'], files['dtb'], files['iomem'].decode())
    if args.out_dtb:
        changes = {('/chosen', 'linux,initrd-start'): struct.pack('>Q', INITRD),
                   ('/chosen', 'linux,initrd-end'): struct.pack('>Q', INITRD + len(files['initramfs']))}
        before, reservations, cpu = read(files['dtb'])
        if '/chosen' not in before:
            ap.error('input DTB must have /chosen')
        prepared = rewrite(files['dtb'], changes)
        after, reservations2, cpu2 = read(prepared)
        if set(before) != set(after) or reservations != reservations2 or cpu != cpu2:
            raise ValueError('unexpected change to nodes/reservations/boot CPU')
        for path in before:
            for name in before[path].keys() | after[path].keys():
                expected = changes.get((path, name), before[path].get(name))
                if after[path].get(name) != expected:
                    raise ValueError('unexpected DT property change')
        report = layout(files['image'], files['initramfs'], prepared, files['iomem'].decode())
        assert report['chosen_initrd_matches']
        # Exclusive creation also protects against overwriting the input file.
        with args.out_dtb.open('xb') as output:
            output.write(prepared)
        report['output_dtb_sha256'] = hashlib.sha256(prepared).hexdigest()
        report['only_chosen_initrd_properties_changed'] = True
    report['sha256'] = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    print(json.dumps(report, indent=2))
