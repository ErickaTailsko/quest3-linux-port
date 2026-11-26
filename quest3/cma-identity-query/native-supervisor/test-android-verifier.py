#!/usr/bin/env python3
"""Synthetic metadata/recorded-report regressions; no NDK or Android execution."""
import importlib.util
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location('android_verifier', Path(__file__).with_name('verify-android-build.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def synthetic():
    blob = bytearray(4096)
    blob[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', blob, 16, 3, 183, 1)
    struct.pack_into('<QQ', blob, 24, 0x700, 64)
    struct.pack_into('<HHH', blob, 52, 64, 56, 7)
    def ph(index, kind, flags, offset, address, size, alignment):
        struct.pack_into('<IIQQQQQQ', blob, 64+56*index, kind, flags, offset, address,
                         address, size, size, alignment)
    ph(0, 1, 5, 0, 0, 0x800, 4096)
    ph(1, 1, 6, 0x800, 0x1800, 0x800, 4096)
    ph(2, 3, 4, 0x240, 0x240, 21, 1)
    ph(3, 0x6474e551, 6, 0, 0, 0, 0)
    ph(4, 0x6474e552, 4, 0x800, 0x1800, 0x100, 1)
    tags = [(1, 0), (1, 8), (0x6ffffffb, 0x08000001), (30, 8), (5, 0x500), (10, 17), (0, 0)]
    ph(5, 2, 6, 0x800, 0x1800, len(tags)*16, 8)
    for i, item in enumerate(tags):
        struct.pack_into('<QQ', blob, 0x800+i*16, *item)
    note = struct.pack('<III', 8, 132, 1)+b'Android\0'+struct.pack('<I', 28)+b'r30\0'.ljust(64,b'\0')+b'16248370\0'.ljust(64,b'\0')
    ph(6, 4, 4, 0x280, 0x280, len(note), 4)
    blob[0x280:0x280+len(note)] = note
    blob[0x240:0x255] = b'/system/bin/linker64\0'
    blob[0x500:0x511] = b'libc.so\0libdl.so\0'
    blob[0x600:0x600+len(m.MESSAGE)] = m.MESSAGE
    return bytes(blob)


def denied(function, *args):
    try:
        function(*args)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid Android artifact/report accepted')


good = synthetic()
result = m.inspect_elf(good)
assert result['pie'] and result['bind_now'] and result['android_api_note'] == 28
assert not result['runtime_compatibility_validated']
for bad in (b'', good[:63], good[:100]):
    denied(m.inspect_elf, bad)
for offset, fmt, value in (
        (4, '<B', 1), (5, '<B', 2), (16, '<H', 2), (18, '<H', 62),
        (24, '<Q', 0x1900), (32, '<Q', 5000), (54, '<H', 32), (56, '<H', 0),
        (64+4, '<I', 7), (64+56+48, '<Q', 3),
        (64+56*2, '<I', 0), (64+56*3+4, '<I', 7), (64+56*4, '<I', 0),
        (64+56*5+32, '<Q', 111), (0x800+2*16+8, '<Q', 1),
        (0x800+3*16+8, '<Q', 4), (0x800+4*16+8, '<Q', 0x9999),
        (0x280+20, '<I', 29), (0x280+4, '<I', 9999)):
    bad = bytearray(good); struct.pack_into(fmt,bad,offset,value)
    denied(m.inspect_elf, bytes(bad))
for before, after in ((b'/system/bin/linker64', b'/lib64/ld-linux-xxxx'),
                      (b'libc.so\0', b'evil.so\0'), (b'Android\0', b'Invalid\0'),
                      (b'16248370', b'00000000')):
    denied(m.inspect_elf, good.replace(before, after))
denied(m.inspect_elf, good+b'--host-fixture')
denied(m.inspect_elf, good+b'Q3_NATIVE_FAULT')

assembly = '''00000000000005d8 <main>:
  5d8: a9bf7bfd stp x29, x30, [sp, #-0x10]!
  5dc: 910003fd mov x29, sp
  5e0: d503201f nop
  5e4: 10fff1e1 adr x1, 0x420 <main.message>
  5e8: 52800040 mov w0, #0x2
  5ec: 52800822 mov w2, #0x41
  5f0: 94000010 bl 0x630 <write@plt>
  5f4: 528009a0 mov w0, #0x4d // =77
  5f8: a8c17bfd ldp x29, x30, [sp], #0x10
  5fc: d65f03c0 ret

'''
ir = 'define hidden i32 @q3_supervise_fixture(ptr %r) !type !1'
for variant, keep in (('disarmed', False), ('core-linkcheck-disarmed', True)):
    flags = sorted(m.FLAGS)+(['-Wl,--undefined=q3_supervise_fixture'] if keep else [])
    symbols = '0 t main\n1 T _start\n'+('2 t q3_supervise_fixture\n' if keep else '')
    symbols += ''.join(' U '+name+'\n' for name in sorted(m.CORE_IMPORTS if keep else {'__libc_init','write'}))
    checked = m.check_reports(flags, symbols, assembly, ir, variant)
    assert checked['main_disassembly_write_then_return_77'] and not checked['scs_enabled']
    for flag in m.FLAGS:
        denied(m.check_reports, [x for x in flags if x != flag], symbols, assembly, ir, variant)
    for flag in ('-DQ3_SUPERVISOR_HOST_TEST', '-flto=thin', '-fno-sanitize=cfi',
                 '-fsanitize=shadow-call-stack', '-fsanitize-recover=cfi'):
        denied(m.check_reports, flags+[flag], symbols, assembly, ir, variant)
    denied(m.check_reports, flags, symbols+' U system\n', assembly, ir, variant)
    denied(m.check_reports, flags, symbols, assembly.replace('write@plt','fork@plt'), ir, variant)
    denied(m.check_reports, flags, symbols, assembly.replace('#0x4d','#0x0'), ir, variant)
    denied(m.check_reports, flags, symbols, assembly.replace('nop','blr'), ir, variant)
    denied(m.check_reports, flags, symbols, assembly, '', variant)
    versions = 'File: libc.so\n'+''.join('Name: '+name+'\n' for name in (['LIBC','LIBC_N','LIBC_P'] if keep else ['LIBC']))
    assert m.check_versions(versions, variant)
    denied(m.check_versions, versions.replace('libc.so','libc.so.6'), variant)
    denied(m.check_versions, versions+'Name: GLIBC_2.17\n', variant)
    denied(m.check_versions, versions+'Name: LIBC\n', variant)
print('PASS Android verifier: synthetic ELF API/NDK/dependencies/NX/RELRO/PIE/NOW plus disarmed main/flags/retained-core reports; no Android execution')
