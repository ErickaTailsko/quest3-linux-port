#!/usr/bin/env python3
"""Summarize captured Linux kpage metadata offline; never allocates or proves ownership."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

BITS = {'locked': 0, 'lru': 5, 'slab': 7, 'buddy_marked': 10, 'anon': 12,
        'compound_head': 15, 'compound_tail': 16, 'unevictable': 18,
        'hwpoison': 19, 'nopage': 20, 'offline': 23, 'pgtable': 26}


def analyze(flags_blob, counts_blob, start=0x90000000, end=0x93400000, page_size=4096):
    if (page_size < 4096 or page_size & (page_size - 1) or start < 0 or
        end <= start or end > 1 << 64 or start % page_size or end % page_size):
        raise ValueError('invalid page size or physical window')
    pages = (end - start) // page_size
    if len(flags_blob) != pages * 8 or len(counts_blob) != pages * 8:
        raise ValueError('metadata byte count differs from requested PFN window')
    flags = [v[0] for v in struct.iter_unpack('<Q', flags_blob)]
    counts = [v[0] for v in struct.iter_unpack('<Q', counts_blob)]
    return {
        'window_start': hex(start), 'window_end_exclusive': hex(end),
        'page_size': page_size, 'pages': pages,
        'flag_counts': {name: sum(bool(value & (1 << bit)) for value in flags)
                        for name, bit in BITS.items()},
        'zero_flag_entries': flags.count(0),
        'nonzero_mapcount_entries': sum(value > 0 for value in counts),
        'flags_sha256': hashlib.sha256(flags_blob).hexdigest(),
        'counts_sha256': hashlib.sha256(counts_blob).hexdigest(),
        'live_metadata_atomic': False,
        'pageblock_migratetypes_identified': False,
        'contiguous_allocation_feasibility_proven': False,
        'allocator_ownership_acquired': False, 'dma_quiescence_proven': False,
        'boot_ready': False,
        'note': 'Snapshots can race and were read separately. Buddy bits mark allocation '
                'heads, not a complete free-page count. Zero flags/mapcount do not prove '
                'free pages. Counts do not establish exclusive ownership, migratability or DMA safety. '
                'Flag meanings assume the reviewed Linux 5.10 UAPI.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flags', type=Path, required=True)
    parser.add_argument('--counts', type=Path, required=True)
    parser.add_argument('--start', type=lambda value: int(value, 0), default=0x90000000)
    parser.add_argument('--end', type=lambda value: int(value, 0), default=0x93400000)
    parser.add_argument('--page-size', type=int, default=4096)
    args = parser.parse_args()
    try:
        result = analyze(args.flags.read_bytes(), args.counts.read_bytes(), args.start, args.end, args.page_size)
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(result, indent=2))
