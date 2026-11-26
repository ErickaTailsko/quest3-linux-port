#!/usr/bin/env python3
"""Compare verified PMSG captures across a kernel boot change; host reads only."""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

def load(name):
    path = Path(__file__).resolve().with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def compare(test, before, after, dtb):
    baseline = load('check-pmsg-baseline').check(test, before, dtb)
    if not baseline['baseline_marker_verified']:
        raise ValueError('pre-reboot marker baseline was not verified')
    marker = baseline['marker'].encode('ascii')
    if not re.fullmatch(rb'Q3_RAW_RETENTION_[0-9a-f]{32}', marker):
        raise ValueError('invalid marker format')
    manifest = json.loads((after / 'manifest.json').read_text())
    data = (after / 'ramoops.bin').read_bytes()
    if (manifest.get('status') != 'verified' or manifest.get('bytes') != len(data) or
        manifest.get('sha256') != hashlib.sha256(data).hexdigest()):
        raise ValueError('post-reboot capture integrity not confirmed')
    boot = manifest.get('boot_id', '')
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', str(boot)) or boot == baseline['boot_id']:
        raise ValueError('a different kernel boot identity is required')
    decoded = load('analyze-snapshot').analyze(data, dtb.read_bytes())
    pmsg = next(region for region in decoded['regions'] if region['name'] == 'pmsg')
    begin = int(pmsg['offset'], 16) + 12
    body = data[begin:begin + pmsg['bytes'] - 12]
    position = baseline['marker_offset_in_pmsg_data']
    found = body.find(marker)
    count = body.count(marker)
    same_slot = body[position:position + len(marker)] == marker
    logical = body[pmsg['start']:pmsg['size']] + body[:pmsg['start']] if pmsg['header_valid'] else b''
    return {'kernel_boot_changed': True, 'boot_id_before': baseline['boot_id'],
            'boot_id_after': boot, 'intermediate_kernel_boot_count_known': False,
            'baseline_marker_verified': True, 'marker': marker.decode(),
            'baseline_offset_in_pmsg_data': position,
            'after_marker_offset_in_pmsg_data': found, 'after_raw_marker_occurrences': count,
            'marker_at_original_offset': same_slot,
            'marker_retention_confirmed': same_slot and count == 1,
            'marker_in_after_logical_ring': marker in logical,
            'after_pmsg_header_valid': pmsg['header_valid'],
            'after_pmsg_start': pmsg['start'], 'after_pmsg_size': pmsg['size'],
            'current_ring_size_reaches_original_marker': pmsg['header_valid'] and pmsg['size'] > position,
            'before_snapshot_sha256': baseline['snapshot_sha256'],
            'after_snapshot_sha256': manifest['sha256'],
            'pmsg_physical_base_from_supplied_dt': baseline['pmsg_physical_base'],
            'shutdown_log_transport_validated': False, 'device_writes_by_comparison': False,
            'note': 'A positive result confirms these raw marker bytes across the observed boot change. '
                    'Absence does not identify the eraser or prove firmware RAM loss. '
                    'This does not validate late kernel-callback logging or other reset modes.'}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('test', 'before', 'after', 'dtb'):
        ap.add_argument('--' + name, type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(compare(args.test, args.before, args.after, args.dtb), indent=2))
