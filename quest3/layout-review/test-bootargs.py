#!/usr/bin/env python3
"""Host-only RAM-first command line transformation checks."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
from fdtcheck import read, rewrite

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bootargs', root / 'prepare-bootargs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
blob = (root.parent / 'usb-minimal/quest3-usb2-peripheral.private.dtb').read_bytes()
original = ('root=/dev/sda rootfstype=ext4 rootflags=rw rootdelay=4 rootwait=10 rootwait rw ro '
            'init=/old rdinit=/old bootconfig console=none loglevel=2 loglevel=3 '
            'panic=1 pstore.compress=deflate keep=value')
blob = rewrite(blob, {('/chosen', 'bootargs'): original.encode() + b'\0'})
target, args = module.prepare(blob)
tokens = args.split()
for key, value in [('rdinit', '/init'), ('loglevel', '7'), ('log_buf_len', '1M'),
                   ('panic', '0'), ('pstore.compress', 'none')]:
    assert [t for t in tokens if t.split('=', 1)[0] == key] == [key + '=' + value]
assert 'keep=value' in tokens
assert not any(t.split('=', 1)[0] in {'root', 'rootfstype', 'rootflags', 'rootdelay', 'rootwait', 'init', 'bootconfig', 'ro', 'rw'} for t in tokens)
before, reservations, cpu = read(blob)
after, reservations2, cpu2 = read(target)
before['/chosen']['bootargs'] = args.encode() + b'\0'
assert before == after and reservations == reservations2 and cpu == cpu2
assert module.prepare(target)[0] == target
for value in [b'quoted="unsupported value"\0', b'bad\0hidden\0']:
    bad = rewrite(blob, {('/chosen', 'bootargs'): value})
    try:
        module.prepare(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('ambiguous command line accepted')
bad = rewrite(blob, {('/', 'compatible'): b'qcom,wrong-board\0'})
try:
    module.prepare(bad)
except ValueError:
    pass
else:
    raise AssertionError('wrong board accepted')
with tempfile.TemporaryDirectory(prefix='qmp-bootargs-') as temporary:
    folder = Path(temporary)
    source, output = folder / 'input.dtb', folder / 'output.dtb'
    source.write_bytes(blob)
    command = [sys.executable, str(root / 'prepare-bootargs.py'), '--input', str(source), '--out', str(output)]
    subprocess.run(command, check=True, capture_output=True)
    assert output.read_bytes() == target
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == target
print('PASS diagnostic bootargs: disk-root removal, unique overrides, board/ambiguity checks, property-only change, idempotence and no overwrite')
