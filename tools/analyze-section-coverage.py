#!/usr/bin/env python3
"""Offline System RAM coverage by ARM64 sections; never proves hot-remove immunity."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('survey', Path(__file__).with_name('plan-memory-survey.py'))
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)
SECTION_BYTES = 128 * 1024 * 1024  # Reviewed ARM64 4KiB-page source configuration.
MAX_SECTIONS = 4096


def analyze(iomem, intervals):
    ram = []
    for line in iomem.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'\s*([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+:\s+(.+)', line)
        if not match:
            raise ValueError('unparsed iomem record')
        lo, hi = int(match[1],16), int(match[2],16)+1
        if lo == 0 and hi == 1:
            raise ValueError('possible address redaction')
        survey.merge([[lo, hi]])  # Validate even non-RAM records.
        if match[3].strip() == 'System RAM':
            ram.append([lo, hi])
    ram = survey.merge(ram)
    if not ram:
        raise ValueError('no System RAM records')
    indices = set()
    if not intervals:
        raise ValueError('no geometric intervals')
    for interval in intervals:
        lo, hi = int(interval['start'],0), int(interval['end_exclusive'],0)
        survey.merge([[lo, hi]])
        first, last = lo//SECTION_BYTES, (hi-1)//SECTION_BYTES
        if last-first+1 > MAX_SECTIONS:
            raise ValueError('section analysis exceeds bounded host scope')
        indices.update(range(first, last+1))
        if len(indices) > MAX_SECTIONS:
            raise ValueError('section analysis exceeds bounded host scope')
    sections = []
    for index in sorted(indices):
        lo, hi = index*SECTION_BYTES, (index+1)*SECTION_BYTES
        missing = survey.subtract([[lo, hi]], ram)
        sections.append({'start':hex(lo), 'end_exclusive':hex(hi),
                         'system_ram_bytes_in_snapshot':SECTION_BYTES-sum(b-a for a,b in missing),
                         'missing_system_ram_ranges':[{'start':hex(a),'end_exclusive':hex(b)} for a,b in missing],
                         'full_system_ram_coverage_in_snapshot':not missing,
                         'normal_offline_hole_precheck_would_reject_same_snapshot':bool(missing)})
    return {'scope':'offline resource coverage only; no RAM lifetime or eligibility decision',
            'section_bytes_assumed_from_reviewed_source':SECTION_BYTES,
            'input_geometric_intervals':len(intervals), 'intersected_sections':len(sections),
            'sections_fully_covered_by_system_ram':sum(s['full_system_ram_coverage_in_snapshot'] for s in sections),
            'sections_with_snapshot_system_ram_holes':sum(not s['full_system_ram_coverage_in_snapshot'] for s in sections),
            'sections':sections, 'system_ram_resource_flags_captured':False,
            'boot_origin_proven':False, 'resource_lifetime_proven':False,
            'normal_hotremove_immunity_proven':False, 'vendor_removal_immunity_proven':False,
            'all_pfns_validated':False, 'new_physical_base_selected':False,
            'survey_ready':False, 'ownership_acquired':False, 'boot_ready':False,
            'note':'Reserved children inside System RAM are not holes for this coverage calculation. '
                    'Holes describe one non-atomic snapshot; later hot-add can change coverage. '
                    'The normal offline precheck is not the vendor subsection-removal path. '
                    'No section, window or base is selected as safe or acquired.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iomem', type=Path, required=True)
    parser.add_argument('--geometry', type=Path, required=True,
                        help='Planner JSON or reviewed map capture with geometry.survey_intervals')
    args = parser.parse_args()
    try:
        iomem, geometry = args.iomem.read_bytes(), args.geometry.read_bytes()
        source = json.loads(geometry)
        if not isinstance(source, dict):
            raise ValueError('geometry input must be a JSON object')
        result = analyze(iomem.decode('utf-8'), source.get('geometry', source)['survey_intervals'])
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, str(error)+'\n')
    result['iomem_sha256'] = hashlib.sha256(iomem).hexdigest()
    result['geometry_input_sha256'] = hashlib.sha256(geometry).hexdigest()
    print(json.dumps(result,indent=2))
