#!/usr/bin/env python3
import importlib.util
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from fdtcheck import read, rewrite

here = Path(__file__).resolve().parent
root = here.parent
spec = importlib.util.spec_from_file_location('checker', here / 'check-layout.py')
checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
image = (root / 'ram-first-kernel/arch/arm64/boot/Image').read_bytes()
initrd = (root / 'usb-minimal/quest3-usb2-minimal.cpio.gz').read_bytes()
dtb = (root / 'usb-minimal/quest3-usb2-peripheral.private.dtb').read_bytes()
iomem = Path(sys.argv[1]).read_text()
assert checker.layout(image, initrd, dtb, iomem)['image_entry'] == '0x90000000'
assert not checker.layout(image, initrd, dtb, iomem)['chosen_initrd_matches']
def reject(k=image, r=initrd, d=dtb, m=iomem):
    try:
        checker.layout(k, r, d, m)
    except ValueError:
        return
    raise AssertionError('unsafe input accepted')
reject(m=iomem + '\n  90100000-90100fff : reserved\n')
reject(m=iomem + '\n  90100000-90100fff : Kernel data\n')
reject(m='00000000-00000000 : System RAM\n')
reject(k=image[:63]); reject(r=b''); reject(r=bytes(0x200001))
reject(d=dtb[:-1]); reject(d=dtb + b'\0')
nodes, _, _ = read(dtb)
reserved_path = next(p for p in nodes if p.startswith('/reserved-memory/') and 'reg' in nodes[p])
reject(d=rewrite(dtb, {(reserved_path, 'reg'): struct.pack('>QQ', 0x90000000, 4096)}))
with tempfile.TemporaryDirectory() as tmp:
    output = Path(tmp) / 'prepared.dtb'
    command = [sys.executable, str(here / 'check-layout.py'), '--image', str(root / 'ram-first-kernel/arch/arm64/boot/Image'),
               '--initramfs', str(root / 'usb-minimal/quest3-usb2-minimal.cpio.gz'),
               '--dtb', str(root / 'usb-minimal/quest3-usb2-peripheral.private.dtb'),
               '--iomem', sys.argv[1], '--out-dtb', str(output)]
    subprocess.run(command, check=True, capture_output=True)
    prepared = output.read_bytes()
    assert checker.layout(image, initrd, prepared, iomem)['chosen_initrd_matches']
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == prepared
print('PASS captured inputs, nested iomem reservations, redacted map, DT reservations, sizes, chosen preparation and overwrite refusal')
