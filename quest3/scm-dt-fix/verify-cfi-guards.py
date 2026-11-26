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
                      'qkx_test_cpus'):
        assert not re.search(r'\b'+forbidden+r'$', symbols, re.M), (name, forbidden)
    assert '__cfi_check' in symbols
    dis = tool('llvm-objdump', '-d', '--no-show-raw-insn', new)
    assert re.search(r'mov\s+w\d+, #-95\b', dis), 'Missing EOPNOTSUPP return'
    if name == 'quest_kexec':
        for exported in ('walk_iomem_res_desc', 'qcom_scm_is_available', 'qcom_scm_io_readl',
                         'qcom_scm_io_writel', 'qcom_scm_sec_wdog_deactivate'):
            assert ' U '+exported in symbols, exported
        for legacy in ('scm_io_read', 'scm_io_write', 'scm_call2', 'scm_is_call_available'):
            assert not re.search(r'\b'+legacy+r'$', symbols, re.M), legacy
        function = dis.split('<qkx_roundtrip>:', 1)[1].split('\n\n', 1)[0]
        assert re.search(r'stp\s+x18, x30, \[sp, #80\]', function)
        assert re.search(r'ldp\s+x18, x30, \[sp, #80\]', function)
        assert re.search(r'stp\s+x19, x20, \[sp, #-96\]!', function)
        assert re.search(r'ldp\s+x19, x20, \[sp\], #96', function)
    else:
        imports = set(tool('llvm-nm', '-u', new).split()) - {'U'}
        assert imports <= {'printk', '__ubsan_handle_cfi_check_fail_abort'}, imports
    print(f'PASS {name}: baseline used kprobes; fixed binary has no private resolver, retains CFI, returns -95')
scm_command = (root/'module/.quest3-scm.o.cmd').read_text().splitlines()[0]
for flag in ('-flto', '-fsanitize=cfi', '-fsanitize=shadow-call-stack', '-ffixed-x18'):
    assert flag in scm_command, flag
assert 'local-include' not in scm_command
assert not re.search(r'error:|warning:|FAILED|\*\*\*', (root/'scm-build.log').read_text())
print('PASS SCM uses exported APIs with CFI/SCS and no legacy header dependency')
print('PASS exported RAM traversal and x18 save/restore in 96-byte aligned frame')
print('Hardware/MMU execution not tested.')
