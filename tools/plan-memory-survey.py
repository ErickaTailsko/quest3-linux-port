#!/usr/bin/env python3
"""Offline historical map geometry for a future metadata survey; no RAM ownership."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'quest3/ramoops-snapshot'))
from fdtcheck import read

BLOCK = 4 * 1024 * 1024
NEEDED = 40 * 1024 * 1024


def merge(intervals):
    result = []
    for lo, hi in sorted(intervals):
        if lo < 0 or hi <= lo or hi > 1 << 64:
            raise ValueError('invalid physical interval')
        if result and lo <= result[-1][1]:
            result[-1][1] = max(hi, result[-1][1])
        else:
            result.append([lo, hi])
    return result


def subtract(intervals, exclusions):
    result = merge(intervals)
    for begin, end in merge(exclusions):
        revised = []
        for lo, hi in result:
            if end <= lo or begin >= hi:
                revised.append([lo, hi])
            else:
                if lo < begin:
                    revised.append([lo, begin])
                if end < hi:
                    revised.append([end, hi])
        result = revised
    return result


def plan(nodes, reserve_map, iomem):
    compat = nodes.get('/', {}).get('compatible', b'').split(b'\0')
    if b'qcom,anorak' not in compat or b'oculus,eureka' not in compat:
        raise ValueError('unsupported board')
    for path in ('/', '/reserved-memory'):
        props = nodes.get(path, {})
        if any(props.get(key) != struct.pack('>I', 2) for key in ('#address-cells', '#size-cells')):
            raise ValueError('unsupported DT cell widths')
    if nodes['/reserved-memory'].get('ranges') != b'':
        raise ValueError('unsupported reserved-memory translation')
    empty_memory = []
    def ranges(data, memory_path=None):
        if not data or len(data) % 16:
            raise ValueError('invalid 64-bit reg tuples')
        result = []
        for lo, size in struct.iter_unpack('>QQ', data):
            # Vendor early_init_dt_scan_memory skips zero-sized memory tuples.
            # Keep them visible; do not extend this exception to reservations.
            if not size and memory_path is not None:
                empty_memory.append({'node': memory_path, 'start': hex(lo)})
                continue
            if not size or lo + size > 1 << 64:
                raise ValueError('invalid DT physical range')
            result.append([lo, lo + size])
        return result
    memory, exclusions, unresolved = [], [], []
    for path, props in nodes.items():
        if props.get('device_type') == b'memory\0' and props.get('status') != b'disabled\0':
            if path.count('/') != 1:
                raise ValueError('unsupported memory node parent addressing')
            memory.extend(ranges(props.get('linux,usable-memory', props.get('reg', b'')), path))
        if path.startswith('/reserved-memory/'):
            if path.count('/') != 2:
                raise ValueError('unsupported nested reserved-memory addressing')
            if 'reg' in props:
                exclusions.extend(ranges(props['reg']))
            elif 'size' in props:
                unresolved.append(path)
    for lo, size in reserve_map:
        if size:
            exclusions.extend(merge([[lo, lo + size]]))
    ram = []
    for line in iomem.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'\s*([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+:\s+(.+)', line)
        if not match:
            raise ValueError('unparsed iomem record')
        lo, hi = int(match[1], 16), int(match[2], 16) + 1
        if lo == 0 and hi == 1:
            raise ValueError('zeroed iomem record; possible address redaction')
        interval = merge([[lo, hi]])
        if match[3].strip() == 'System RAM':
            ram.extend(interval)
        else:
            exclusions.extend(interval)
    intersection = []
    for a, b in merge(memory):
        for c, d in merge(ram):
            if max(a, c) < min(b, d):
                intersection.append([max(a, c), min(b, d)])
    if not intersection:
        raise ValueError('no DT/iomem RAM intersection; redacted or incompatible captures')
    # Already studied mixed-type window; do not treat it as a new destination.
    exclusions.append([0x90000000, 0x93400000])
    intervals = []
    for lo, hi in subtract(intersection, exclusions):
        lo = (lo + BLOCK - 1) // BLOCK * BLOCK
        hi = hi // BLOCK * BLOCK
        if hi - lo >= NEEDED:
            intervals.append({'start': hex(lo), 'end_exclusive': hex(hi),
                              'pageblocks': (hi - lo) // BLOCK,
                              'overlapping_40mib_geometry_windows': (hi - lo - NEEDED) // BLOCK + 1})
    return {'scope': 'historical DT/iomem geometry for planning only',
            'pageblock_bytes_assumed': BLOCK, 'relative_payload_window_bytes': NEEDED,
            'survey_intervals': intervals, 'dynamic_reservations_without_reg': unresolved,
            'ignored_zero_size_memory_tuples': empty_memory,
            'reservation_geometry_complete': not unresolved,
            'new_physical_base_selected': False, 'survey_executed': False,
            'current_boot_provenance_confirmed': False, 'pageblock_types_known_here': False,
            'all_pfns_validated': False, 'ownership_acquired': False, 'boot_ready': False,
            'note': 'Resource holes are not free pages. Intervals may contain occupied, '
                    'UNMOVABLE or CMA pages, multiple zones and DMA mappings. Fresh matching '
                    'captures and a separately reviewed/authorized bounded survey are required. '
                    'No module address list or acquisition command is generated.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--iomem', type=Path, required=True)
    args = parser.parse_args()
    try:
        blob, text = args.dtb.read_bytes(), args.iomem.read_bytes()
        nodes, reservations, _ = read(blob)
        result = plan(nodes, reservations, text.decode())
    except (OSError, ValueError, KeyError, UnicodeError, struct.error) as error:
        parser.exit(2, str(error) + '\n')
    result['dtb_sha256'] = hashlib.sha256(blob).hexdigest()
    result['iomem_sha256'] = hashlib.sha256(text).hexdigest()
    print(json.dumps(result, indent=2))
