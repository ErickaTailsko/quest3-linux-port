#!/usr/bin/env python3
"""Confirm a padded marker's actual location in a verified pre-reboot snapshot."""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

def check(test, capture, dtb):
    metadata = json.loads((test / 'test.json').read_text())
    manifest = json.loads((capture / 'manifest.json').read_text())
    data = (capture / 'ramoops.bin').read_bytes()
    if (manifest.get('status') != 'verified' or manifest.get('bytes') != len(data) or
        manifest.get('sha256') != hashlib.sha256(data).hexdigest()):
        raise ValueError('snapshot integrity not confirmed')
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', str(manifest.get('boot_id', ''))):
        raise ValueError('invalid baseline kernel boot identity')
    if manifest.get('boot_id') != metadata.get('boot_id_before_write'):
        raise ValueError('boot changed before baseline capture')
    marker = metadata['marker'].encode('ascii')
    if not re.fullmatch(rb'Q3_RAW_RETENTION_[0-9a-f]{32}', marker):
        raise ValueError('unexpected test marker')
    path = Path(__file__).resolve().with_name('analyze-snapshot.py')
    spec = importlib.util.spec_from_file_location('snapshot_decoder', path)
    decoder = importlib.util.module_from_spec(spec); spec.loader.exec_module(decoder)
    decoded = decoder.analyze(data, dtb.read_bytes())
    pmsg = next(region for region in decoded['regions'] if region['name'] == 'pmsg')
    begin = int(pmsg['offset'], 16) + 12
    body = data[begin:begin + pmsg['bytes'] - 12]
    location = body.find(marker)
    logical = body[pmsg['start']:pmsg['size']] + body[:pmsg['start']] if pmsg['header_valid'] else b''
    suitable = (metadata.get('pmsg_write_attempted') is True and pmsg['header_valid'] and
                marker in logical and body.count(marker) == 1 and
                65536 <= location and location + len(marker) <= len(body) - 4096)
    return {'baseline_marker_verified': suitable, 'marker': marker.decode(),
            'marker_offset_in_pmsg_data': location, 'boot_id': manifest['boot_id'],
            'snapshot_sha256': manifest['sha256'], 'pmsg_start': pmsg['start'],
            'pmsg_size': pmsg['size'],
            'pmsg_physical_base': hex(int(decoded['physical_base_from_dt'], 16) + int(pmsg['offset'], 16)),
            'retention_validated': False, 'reboot_requested': False,
            'note': 'This verifies only the baseline. A separate post-reboot snapshot is still required.'}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--test', type=Path, required=True)
    ap.add_argument('--capture', type=Path, required=True)
    ap.add_argument('--dtb', type=Path, required=True)
    args = ap.parse_args()
    result = check(args.test, args.capture, args.dtb)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['baseline_marker_verified'] else 2)
