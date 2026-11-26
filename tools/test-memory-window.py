#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location('memory', Path(__file__).with_name('analyze-memory-window.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
flags = struct.pack('<4Q', 1 << 7, 1 << 26, 1 << 10, 0)
counts = struct.pack('<4Q', 0, 0, 0, 2)
result = module.analyze(flags, counts, 0x10000, 0x14000)
assert result['pages'] == 4
assert result['flag_counts']['slab'] == result['flag_counts']['pgtable'] == result['flag_counts']['buddy_marked'] == 1
assert result['zero_flag_entries'] == result['nonzero_mapcount_entries'] == 1
for key in ['live_metadata_atomic', 'pageblock_migratetypes_identified',
            'contiguous_allocation_feasibility_proven', 'allocator_ownership_acquired',
            'dma_quiescence_proven', 'boot_ready']:
    assert result[key] is False
for bad_flags, bad_counts, start, end, page in [
    (flags[:-1], counts, 0x10000, 0x14000, 4096),
    (flags, counts[:-8], 0x10000, 0x14000, 4096),
    (flags, counts, 0x10001, 0x14000, 4096),
    (flags, counts, 0x14000, 0x10000, 4096),
    (flags, counts, 0x10000, 0x14000, 0),
    (flags, counts, 0x10000, 0x14000, 6000),
    (flags, counts, 0x10000, 1 << 65, 4096),
]:
    try:
        module.analyze(bad_flags, bad_counts, start, end, page)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid metadata accepted')
print('PASS memory metadata: flags, mapcounts, bounds/length validation; no ownership, free-page or DMA-safety inference')
