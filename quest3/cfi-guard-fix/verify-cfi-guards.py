#!/usr/bin/env python3
"""Check linked ARM64 artifacts, not just source; no device execution."""
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
llvm = root / 'clang-prebuilts/clang-r450784e/bin'
def tool(name, *args):
    return subprocess.check_output([str(llvm/name), *map(str, args)], text=True)

for name in ('quest_kexec', 'usb_log'):
    old = root/'inputs/quest-kexec/module'/f'{name}.ko'
    new = root/'module'/f'{name}.ko'
    assert 'register_kprobe' in tool('llvm-nm', '-u', old), 'Negative control no longer exercises private resolver'
    symbols = tool('llvm-nm', new)
    for forbidden in ('register_kprobe', 'unregister_kprobe', 'lookup', 'qkx_execute',
                      'qkx_test_cpus', 'qkx_core_hang_configure', 'qkx_secure_watchdog_configure'):
        assert not re.search(r'\b'+forbidden+r'$', symbols, re.M), (name, forbidden)
    assert '__cfi_check' in symbols
    dis = tool('llvm-objdump', '-d', '--no-show-raw-insn', new)
    assert re.search(r'mov\s+w\d+, #-95\b', dis), 'Missing EOPNOTSUPP return'
    if name == 'quest_kexec':
        assert ' U walk_iomem_res_desc' in symbols
        function = dis.split('<qkx_roundtrip>:', 1)[1].split('\n\n', 1)[0]
        assert re.search(r'stp\s+x18, x30, \[sp, #80\]', function)
        assert re.search(r'ldp\s+x18, x30, \[sp, #80\]', function)
        assert re.search(r'stp\s+x19, x20, \[sp, #-96\]!', function)
        assert re.search(r'ldp\s+x19, x20, \[sp\], #96', function)
    else:
        imports = set(tool('llvm-nm', '-u', new).split()) - {'U'}
        assert imports <= {'printk', '__ubsan_handle_cfi_check_fail_abort'}, imports
    print(f'PASS {name}: baseline used kprobes; fixed binary has no private resolver, retains CFI, returns -95')
print('PASS exported RAM traversal and x18 save/restore in 96-byte aligned frame')
print('Hardware/MMU execution not tested.')
