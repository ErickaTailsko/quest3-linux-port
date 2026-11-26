#!/usr/bin/env python3
"""Forensic raw-byte search, not a claim that logs survived a particular reboot."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from fdtcheck import read

MARKERS = [b'Q3_PSTORE_TEST_KGLaZm_01', b'Q3_PMSG_RETENTION_TEST_01', b'q3_handoff_observer:']
SIGNATURE = 0x43474244
VERSION = (5 << 16) | (10 << 8) | 246

def analyze(blob, dtb):
    nodes, _, _ = read(dtb)
    candidates = [props for path, props in nodes.items() if path.startswith('/reserved-memory/') and
                  b'ramoops' in props.get('compatible', b'').split(b'\0')]
    if len(candidates) != 1:
        raise ValueError('expected one reserved-memory ramoops node')
    props = candidates[0]
    def u32(name):
        value = props.get(name, bytes(4))
        if len(value) != 4:
            raise ValueError('invalid property ' + name)
        return struct.unpack('>I', value)[0]
    if len(props.get('reg', b'')) != 16:
        raise ValueError('unsupported ramoops reg')
    address, total = struct.unpack('>QQ', props['reg'])
    if total != len(blob) or not 4096 <= total <= 1048576:
        raise ValueError('snapshot size differs from DT reservation')
    if u32('ecc-size') or u32('flags') or u32('mem-type'):
        raise ValueError('ECC, per-CPU flags or alternate memory type not supported')
    sizes = {name: u32(name + '-size') for name in ('record', 'console', 'ftrace', 'pmsg')}
    sizes = {name: 1 << (size.bit_length() - 1) if size else 0 for name, size in sizes.items()}
    dump = total - sizes['console'] - sizes['ftrace'] - sizes['pmsg']
    if dump <= 0 or not sizes['record'] or dump < sizes['record']:
        raise ValueError('unsupported ramoops partitioning')
    count = dump // sizes['record']
    zone = (dump // count) & ~1
    regions = [(f'dmesg-{n}', zone, SIGNATURE) for n in range(count)]
    regions += [(name, sizes[name], SIGNATURE ^ (VERSION if name == 'ftrace' else 0))
                for name in ('console', 'ftrace', 'pmsg') if sizes[name]]
    offset = 0
    result = []
    for name, length, expected in regions:
        if length < 12 or offset + length > len(blob):
            raise ValueError('invalid zone boundary')
        sig, start, size = struct.unpack_from('<III', blob, offset)
        data = blob[offset + 12:offset + length]
        valid = sig == expected and start <= size <= len(data)
        logical = data[start:size] + data[:start] if valid else b''
        found = []
        for marker in MARKERS:
            position = data.find(marker)
            if position >= 0 or marker in logical:
                found.append({'marker': marker.decode(), 'raw_offset': offset + 12 + position if position >= 0 else None,
                              'in_current_logical_ring': marker in logical,
                              'proves_specific_reboot_retention': False})
        result.append({'name': name, 'offset': hex(offset), 'bytes': length,
                       'signature': hex(sig), 'header_valid': valid, 'start': start, 'size': size,
                       'markers': found})
        offset += length
    if offset != total:
        raise ValueError('layout has unaccounted tail; requires review')
    return {'snapshot_sha256': hashlib.sha256(blob).hexdigest(), 'dtb_sha256': hashlib.sha256(dtb).hexdigest(),
            'physical_base_from_dt': hex(address), 'bytes': len(blob), 'regions': result,
            'retention_validated': False, 'live_snapshot_atomic': False,
            'note': 'Residual bytes can outlive cleared headers. Absence does not prove firmware clearing.'}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot', type=Path, required=True)
    ap.add_argument('--dtb', type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(analyze(args.snapshot.read_bytes(), args.dtb.read_bytes()), indent=2))
