#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location('geometry', Path(__file__).with_name('plan-payload-geometry.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
image = bytearray(64)
image[56:60] = b'ARM\x64'
struct.pack_into('<QQQ', image, 8, 0, 0x2b20000, 0xa)
sample = {'sample_completed_once': True, 'sample': {'blocks': [
    {'physical_base': hex(0x90000000+i*0x400000), 'zone': 'DMA',
     'migratetype': 'UNMOVABLE' if i in (3, 6) else 'MOVABLE', 'head_reserved': False}
    for i in range(13)]}}
r = module.analyze(image, sample)
assert [run['bytes'] for run in r['sampled_movable_runs']] == [12*module.MIB, 8*module.MIB, 24*module.MIB]
assert not r['image_fits_any_observed_movable_run_geometrically']
assert r['relative_conservative_slot_plan']['total_window_bytes'] == 48*module.MIB
assert r['selected_new_physical_base'] is None and not r['ownership_acquired'] and not r['boot_ready']
for index in (3, 6): sample['sample']['blocks'][index]['migratetype'] = 'MOVABLE'
assert module.analyze(image, sample)['image_fits_any_observed_movable_run_geometrically']
assert not module.analyze(image, sample)['ownership_acquired']
for index in range(13): sample['sample']['blocks'][index]['migratetype'] = 'CMA'
assert module.analyze(image, sample)['longest_sampled_run_bytes'] == 0
bad = copy.deepcopy(sample)
bad['sample']['blocks'][0]['physical_base'] = '0x80000000'
for invalid in [bad, {}, {'sample_completed_once': True, 'sample': {'blocks': []}}]:
    try: module.analyze(image, invalid)
    except (ValueError, KeyError): pass
    else: raise AssertionError('invalid sample accepted')
for offset, size, flags in [(0, 63, 0xa), (0, 0, 0xa), (0, 0x2b20000, 2), (0x1000, 0x2b20000, 0xa)]:
    bad_image = bytearray(image)
    struct.pack_into('<QQQ', bad_image, 8, offset, size, flags)
    try: module.analyze(bad_image, sample)
    except ValueError: pass
    else: raise AssertionError('invalid Image accepted')
print('PASS payload geometry: observed runs, declared image size, slot rounding, CMA separation, bad evidence and no ownership/base selection')
