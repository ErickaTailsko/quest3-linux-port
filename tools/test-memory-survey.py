#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location('survey', Path(__file__).with_name('plan-memory-survey.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.subtract([[0, 100]], [[20, 30], [25, 40], [80, 120]]) == [[0, 20], [40, 80]]
assert module.merge([[20, 40], [0, 20], [10, 30]]) == [[0, 40]]
cells = {'#address-cells': struct.pack('>I', 2), '#size-cells': struct.pack('>I', 2)}
nodes = {'/': {**cells, 'compatible': b'oculus,eureka\0qcom,anorak\0'},
         '/reserved-memory': {**cells, 'ranges': b''},
         '/memory@100000000': {'device_type': b'memory\0', 'reg': struct.pack('>QQ', 0x100000000, 128*1024*1024)}}
iomem = '100000000-107ffffff : System RAM\n  104000000-1047fffff : reserved\n'
r = module.plan(nodes, [], iomem)
assert len(r['survey_intervals']) == 2
assert r['survey_intervals'][0]['pageblocks'] == 16
assert r['survey_intervals'][1]['start'] == '0x104800000'
assert module.plan(nodes, [(0x100000000, 128*1024*1024)], iomem)['survey_intervals'] == []
empty = copy.deepcopy(nodes)
empty['/memory@100000000']['reg'] += struct.pack('>QQ', 0xd8800000, 0)
empty_result = module.plan(empty, [], iomem)
assert empty_result['survey_intervals'] == r['survey_intervals']
assert empty_result['ignored_zero_size_memory_tuples'] == [{'node': '/memory@100000000', 'start': '0xd8800000'}]
usable = copy.deepcopy(nodes)
usable['/memory@100000000']['linux,usable-memory'] = struct.pack('>QQ', 0x100000000, 4*1024*1024)
assert module.plan(usable, [], iomem)['survey_intervals'] == []
fixed = copy.deepcopy(nodes)
fixed['/memory@100000000']['reg'] = struct.pack('>QQ', 0x90000000, 52*1024*1024)
assert module.plan(fixed, [], '90000000-933fffff : System RAM')['survey_intervals'] == []
for key in ['new_physical_base_selected', 'survey_executed', 'current_boot_provenance_confirmed', 'ownership_acquired', 'boot_ready']:
    assert r[key] is False
dynamic = copy.deepcopy(nodes)
dynamic['/reserved-memory/dynamic'] = {'size': struct.pack('>Q', 0x1000)}
assert not module.plan(dynamic, [], iomem)['reservation_geometry_complete']
blocked = copy.deepcopy(nodes)
blocked['/reserved-memory/block'] = {'reg': struct.pack('>QQ', 0x100000000, 128*1024*1024)}
assert module.plan(blocked, [], iomem)['survey_intervals'] == []
wrong = copy.deepcopy(nodes)
wrong['/']['#address-cells'] = struct.pack('>I', 1)
zero_reserved = copy.deepcopy(nodes)
zero_reserved['/reserved-memory/zero'] = {'reg': struct.pack('>QQ', 0x100000000, 0)}
overflow = copy.deepcopy(nodes)
overflow['/memory@100000000']['reg'] = struct.pack('>QQ', (1 << 64) - 1, 2)
nested = copy.deepcopy(nodes)
nested['/reserved-memory/bus/child'] = {'reg': struct.pack('>QQ', 0x100000000, 4096)}
for bad_nodes, bad_map in [(wrong, iomem), (nodes, 'unparsed reserved resource'),
                            (zero_reserved, iomem), (overflow, iomem), (nested, iomem),
                            (nodes, '0-0 : System RAM\n'),
                            (nodes, iomem + '0-0 : reserved\n')]:
    try: module.plan(bad_nodes, [], bad_map)
    except ValueError: pass
    else: raise AssertionError('invalid map accepted')
print('PASS survey geometry: interval subtraction, nested exclusions, 64-bit banks, dynamic reservations, invalid captures and no ownership/deployment claim')
