#!/usr/bin/env python3
"""Synthetic section accounting; no ADB, PFN access, tracing or hotplug."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('sections', Path(__file__).with_name('analyze-section-coverage.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
base = 0x800000000
section = m.SECTION_BYTES
def interval(lo, hi):
    return {'start':hex(lo), 'end_exclusive':hex(hi)}
full = f'{base:x}-{base+2*section-1:x} : System RAM\n'
reserved_child = f'  {base+4096:x}-{base+8191:x} : reserved\n'
r = m.analyze(full+reserved_child, [interval(base+4096,base+section+4096)])
assert r['intersected_sections']==r['sections_fully_covered_by_system_ram']==2
assert r['sections_with_snapshot_system_ram_holes']==0
# Resource children do not subtract from walk_system_ram coverage.
assert r['sections'][0]['system_ram_bytes_in_snapshot']==section
hole_map = (f'{base:x}-{base+section//2-1:x} : System RAM\n'
            f'{base+section//2+4096:x}-{base+section-1:x} : System RAM\n')
r = m.analyze(hole_map,[interval(base,base+4096)])
assert r['intersected_sections']==r['sections_with_snapshot_system_ram_holes']==1
assert r['sections'][0]['system_ram_bytes_in_snapshot']==section-4096
assert r['sections'][0]['normal_offline_hole_precheck_would_reject_same_snapshot']
assert r['sections'][0]['missing_system_ram_ranges']==[interval(base+section//2,base+section//2+4096)]
for key in ['boot_origin_proven','resource_lifetime_proven','normal_hotremove_immunity_proven',
            'vendor_removal_immunity_proven','all_pfns_validated','new_physical_base_selected',
            'survey_ready','ownership_acquired','boot_ready']:
    assert r[key] is False
# Duplicated/nested RAM records must not inflate coverage.
assert m.analyze(full+full,[interval(base,base+section)])['sections'][0]['system_ram_bytes_in_snapshot']==section
for text, intervals in [('not an iomem map',[interval(base,base+4096)]),
                        ('0-0 : System RAM',[interval(base,base+4096)]),
                        ('1000-1fff : reserved',[interval(base,base+4096)]),
                        (full,[]),(full,[interval(base,base)]),
                        (full,[interval(0,1<<65)]),
                        (full,[interval(0,section*(m.MAX_SECTIONS+1))])]:
    try:m.analyze(text,intervals)
    except ValueError:pass
    else:raise AssertionError('invalid/unbounded input accepted')
print('PASS section coverage: 64-bit banks, boundary crossing, reserved children, outside-window holes, nested resources, input/bounds refusal and no immunity/ownership inference')
