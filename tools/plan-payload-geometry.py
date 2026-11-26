#!/usr/bin/env python3
"""Offline geometry from an Image and sampled block types, never a RAM reservation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

MIB = 1024 * 1024


def analyze(image, sample):
    if len(image) < 64 or image[56:60] != b'ARM\x64':
        raise ValueError('not a raw ARM64 Image')
    offset, size, flags = struct.unpack_from('<QQQ', image, 8)
    if (offset not in (0, 0x80000) or size < len(image) or not size or
        flags & 1 or flags & 6 not in (0, 2) or not flags & 8):
        raise ValueError('unsupported Image header')
    if sample.get('sample_completed_once') is not True:
        raise ValueError('completed sample evidence required')
    blocks = sample.get('sample', {}).get('blocks', [])
    if len(blocks) != 13:
        raise ValueError('expected 13 reviewed pageblocks')
    runs = []
    for index, block in enumerate(blocks):
        address = int(block['physical_base'], 16)
        if address != 0x90000000 + index * 4 * MIB:
            raise ValueError('unexpected or unordered sample address')
        if block.get('zone') != 'DMA' or not isinstance(block.get('head_reserved'), bool):
            raise ValueError('unexpected sample zone or reserved flag')
        if block.get('migratetype') not in {'MOVABLE', 'UNMOVABLE', 'RECLAIMABLE', 'CMA', 'HIGHATOMIC', 'ISOLATE'}:
            raise ValueError('unknown migratetype')
        # Do not blend CMA and MOVABLE or infer that a head proves all PFNs.
        if block['migratetype'] != 'MOVABLE' or block['head_reserved']:
            continue
        if runs and runs[-1][1] == address:
            runs[-1][1] += 4 * MIB
        else:
            runs.append([address, address + 4 * MIB])
    image_slot = (offset + size + 2 * MIB - 1) // (2 * MIB) * (2 * MIB)
    longest = max((end - start for start, end in runs), default=0)
    return {
        'scope': 'geometry of observed MOVABLE runs, not allocation feasibility or current state',
        'image_sha256': hashlib.sha256(image).hexdigest(),
        'image_file_bytes': len(image), 'required_image_bytes': size,
        'image_text_offset': hex(offset), 'image_base_alignment': 2 * MIB,
        'header_allows_placement_away_from_ram_base': True,
        'sampled_movable_runs': [{'start': hex(start), 'end_exclusive': hex(end),
                                  'bytes': end-start} for start, end in runs],
        'longest_sampled_run_bytes': longest,
        'image_fits_any_observed_movable_run_geometrically': longest >= offset + size,
        'relative_conservative_slot_plan': {
            'image_slot_bytes': image_slot,
            'initrd_offset_from_base': hex(image_slot),
            'initrd_capacity_bytes': 2 * MIB,
            'dtb_offset_from_base': hex(image_slot + 2 * MIB),
            'dtb_capacity_bytes': 2 * MIB,
            'total_window_bytes': image_slot + 4 * MIB,
        },
        'selected_new_physical_base': None,
        'all_pfns_validated': False, 'ownership_acquired': False,
        'current_boot_layout_validated': False, 'boot_ready': False,
        'note': 'Sample types can change after CPUs resume. Source scatter pages are not '
                'permission for a physically scattered final Image. The relative plan retains '
                '2 MiB initrd/DT slots and does not validate a new DT, reservations, initrd '
                'placement constraints, DMA or loader relocation support.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--sample', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.image.read_bytes(), json.loads(args.sample.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(result, indent=2))
