#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import struct
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('--dtb', type=Path, default=root.parent / 'usb-minimal/quest3-usb2-peripheral.private.dtb')
args = ap.parse_args()
spec = importlib.util.spec_from_file_location('comparator', root / 'compare-pmsg-reboot.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
old_boot = '12345678-1234-1234-1234-123456789abc'
new_boot = 'aaaaaaaa-1234-1234-1234-123456789abc'
marker = ('Q3_RAW_RETENTION_' + '1' * 32).encode()
offset = 68262; begin = 0x70000 + 12
before = bytearray(0x90000)
before[begin + offset:begin + offset + len(marker)] = marker
struct.pack_into('<III', before, 0x70000, 0x43474244, offset + 50, offset + 50)

def save(folder, blob, boot):
    folder.mkdir(exist_ok=True)
    (folder / 'ramoops.bin').write_bytes(blob)
    (folder / 'manifest.json').write_text(json.dumps({'status': 'verified', 'bytes': len(blob),
        'sha256': hashlib.sha256(blob).hexdigest(), 'boot_id': boot}))

with tempfile.TemporaryDirectory() as temp:
    test = Path(temp); first = test / 'before'; second = test / 'after'
    (test / 'test.json').write_text(json.dumps({'marker': marker.decode(),
        'pmsg_write_attempted': True, 'boot_id_before_write': old_boot}))
    save(first, before, old_boot)
    for mode in ['retained-residual', 'missing', 'overwritten', 'shifted', 'duplicated', 'same-boot', 'bad-hash',
                 'bad-before-size', 'bad-after-size', 'bad-before-boot', 'bad-after-boot']:
        save(first, before, old_boot)
        (test / 'test.json').write_text(json.dumps({'marker': marker.decode(),
            'pmsg_write_attempted': True, 'boot_id_before_write': old_boot}))
        blob = bytearray(before)
        struct.pack_into('<II', blob, 0x70000 + 4, 2048, 2048)
        blob[begin:begin + 2048] = b'N' * 2048
        if mode in ['missing', 'overwritten', 'shifted']:
            blob[begin + offset:begin + offset + len(marker)] = bytes(len(marker))
        if mode == 'overwritten':
            struct.pack_into('<II', blob, 0x70000 + 4, 4096, 0x20000 - 12)
        if mode == 'shifted':
            blob[begin + offset + 100:begin + offset + 100 + len(marker)] = marker
        if mode == 'duplicated':
            blob[begin + offset + 100:begin + offset + 100 + len(marker)] = marker
        save(second, blob, old_boot if mode == 'same-boot' else new_boot)
        if mode == 'bad-hash':
            (second / 'ramoops.bin').write_bytes(bytes(len(blob)))
        if mode in ['bad-before-size', 'bad-after-size', 'bad-before-boot', 'bad-after-boot']:
            folder = first if mode.startswith('bad-before') else second
            manifest = json.loads((folder / 'manifest.json').read_text())
            if mode.endswith('size'):
                manifest['bytes'] += 1
            else:
                manifest['boot_id'] = '-' * 36
                if folder == first:
                    metadata = json.loads((test / 'test.json').read_text())
                    metadata['boot_id_before_write'] = manifest['boot_id']
                    (test / 'test.json').write_text(json.dumps(metadata))
            (folder / 'manifest.json').write_text(json.dumps(manifest))
        if mode in ['same-boot', 'bad-hash', 'bad-before-size', 'bad-after-size', 'bad-before-boot', 'bad-after-boot']:
            try: module.compare(test, first, second, args.dtb)
            except ValueError: pass
            else: raise AssertionError('invalid inputs accepted: ' + mode)
            continue
        result = module.compare(test, first, second, args.dtb)
        assert result['marker_retention_confirmed'] == (mode == 'retained-residual'), mode
        assert not result['shutdown_log_transport_validated']
        if mode == 'retained-residual':
            assert not result['marker_in_after_logical_ring']
        if mode == 'overwritten':
            assert result['current_ring_size_reaches_original_marker']
print('PASS paired capture: residual retained marker, missing/overwritten/shifted/duplicated marker, unchanged boot and corrupted capture; no false handoff/log-transport claim')
