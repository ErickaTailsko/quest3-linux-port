#!/usr/bin/env python3
"""Synthetic ELF/flags/provenance regressions, not a kernel module or runtime test."""
import importlib.util
from pathlib import Path
import struct
import tempfile

spec = importlib.util.spec_from_file_location('identity_verifier', Path(__file__).with_name('verify-cma-identity-module.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
versions = {name: i for i, name in enumerate(sorted(m.IMPORTS), 1)}
stock = ''.join(f'0x{crc:08x}\t{name}\tvmlinux\tEXPORT_SYMBOL_GPL\n' for name, crc in versions.items())
defined = {'__cfi_check', 'init_module', 'cleanup_module', 'report_show',
           '__cfi_jt_init_module', '__cfi_jt_cleanup_module', '__param_inspect', '__param_attempt'}
metadata = ('vermagic='+m.VERMAGIC+'\0name='+m.NAME+'\0license=GPL\0depends=\0'
            'parmtype=inspect:bool\0parmtype=attempt:string\0').encode()


def elf(*, records=None, undefined=None, definitions=None, info=metadata):
    records = list(versions.items()) if records is None else records
    undefined = m.IMPORTS-{'module_layout'} if undefined is None else undefined
    definitions = defined if definitions is None else definitions
    strings = bytearray(b'\0')
    symbols = bytearray(24)
    for names, section in ((undefined, 0), (definitions, 1)):
        for name in sorted(names):
            offset = len(strings)
            strings.extend(name.encode()+b'\0')
            symbols.extend(struct.pack('<IBBHQQ', offset, 0x12, 0, section, 0, 0))
    version_data = b''.join(struct.pack('<Q', crc)+name.encode().ljust(56, b'\0') for name, crc in records)
    names = ['', '.text', '.modinfo', '__versions', '.strtab', '.symtab', '.shstrtab']
    name_table = bytearray(b'\0')
    offsets = [0]
    for name in names[1:]:
        offsets.append(len(name_table))
        name_table.extend(name.encode()+b'\0')
    payloads = [b'', b'\0'*4, info, version_data, bytes(strings), bytes(symbols), bytes(name_table)]
    blob = bytearray(64)
    headers = []
    for i, payload in enumerate(payloads):
        offset = len(blob)
        blob.extend(payload)
        kind = 0 if i == 0 else 2 if i == 5 else 3 if i in (4,6) else 1
        headers.append(struct.pack('<IIQQQQIIQQ', offsets[i], kind, 0, 0,
                                   offset, len(payload), 4 if i == 5 else 0,
                                   0, 1, 24 if i == 5 else 0))
    table_offset = len(blob)
    blob.extend(b''.join(headers))
    blob[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', blob, 16, 1, 183, 1)
    struct.pack_into('<Q', blob, 40, table_offset)
    struct.pack_into('<HHHHHH', blob, 52, 64, 0, 0, 64, len(headers), 6)
    return bytes(blob)


def rejected(function, *args):
    try:
        function(*args)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid artifact/flags accepted')


good = elf()
assert m.inspect_module(good, stock)['all_import_crcs_match_supplied_stock']
for bad in (b'', good[:63], good[:-1]):
    rejected(m.inspect_module, bad, stock)
for offset, fmt, value in ((4, '<B', 1), (5, '<B', 2), (16, '<H', 2), (18, '<H', 62),
                            (40, '<Q', len(good)), (52, '<H', 63), (58, '<H', 32),
                            (60, '<H', 0), (62, '<H', 99)):
    bad = bytearray(good); struct.pack_into(fmt, bad, offset, value)
    rejected(m.inspect_module, bytes(bad), stock)
for bad in (elf(records=list(versions.items())[:-1]),
            elf(records=list(versions.items())+[('cma_alloc', 1)]),
            elf(records=list(versions.items())+[next(iter(versions.items()))]),
            elf(records=[(name, crc+1) for name, crc in versions.items()]),
            elf(records=[(name, 1 << 32) for name in versions]),
            elf(undefined=m.IMPORTS-{'module_layout', 'cma_get_name'}),
            elf(undefined=(m.IMPORTS-{'module_layout'}) | {'cma_alloc'}),
            elf(definitions=defined-{'__cfi_check'}),
            elf(info=metadata.replace(b'aarch64', b'other')),
            elf(info=metadata+b'license=GPL\0'),
            elf(info=metadata.replace(b'attempt:string', b'attempt:bool'))):
    rejected(m.inspect_module, bad, stock)
rejected(m.inspect_module, good, stock.replace('vmlinux', 'another-module', 1))
rejected(m.inspect_module, good, '\n'.join(stock.splitlines()[1:]))
rejected(m.inspect_module, good, stock+stock.splitlines()[0]+'\n')
for cfi in (True, False):
    required = m.BASE_FLAGS | (m.CFI_FLAGS if cfi else frozenset())
    command = 'cmd_test := clang ' + ' '.join(sorted(required))
    m.check_command(command, cfi)
    for flag in required:
        rejected(m.check_command, command.replace(flag, ''), cfi)
    for flag in ('-flto=thin', '-fno-lto', '-fno-sanitize=cfi', '-fno-stack-protector',
                 '-fsanitize-recover=cfi', '-fno-sanitize-cfi-cross-dso'):
        rejected(m.check_command, command+' '+flag, cfi)
config = ''.join('CONFIG_'+key+'=y\n' for key in m.REQUIRED)
m.check_config(config)
for key in m.REQUIRED:
    rejected(m.check_config, config.replace('CONFIG_'+key+'=y\n', ''))
for key in ('CFI_PERMISSIVE', 'LTO_CLANG_THIN', 'OF_DYNAMIC', 'OF_OVERLAY'):
    rejected(m.check_config, config+'CONFIG_'+key+'=y\n')

with tempfile.TemporaryDirectory(prefix='cma-module-fixture-') as temporary:
    root = Path(temporary)
    module = root/(m.NAME+'.ko'); module.write_bytes(good)
    source = root/'reviewed.c'; source.write_text('/* synthetic source, not kernel code */\n')
    module.with_suffix('.c').write_bytes(source.read_bytes())
    symvers = root/'stock.symvers'; symvers.write_text(stock)
    runtime = root/'stock.config'; runtime.write_text(config)
    (root/'.config').write_text(config)
    (root/'Module.symvers').write_text(stock)
    release = root/'include/config/kernel.release'; release.parent.mkdir(parents=True)
    release.write_text(m.VERMAGIC.split()[0]+'\n')
    m.CONFIG_HASH = m.STOCK_CONFIG_HASH = m.digest(config.encode())
    m.SYMVERS_HASH = m.digest(stock.encode())
    for suffix, cfi in (('.o.cmd', True), ('.mod.o.cmd', False)):
        flags = m.BASE_FLAGS | (m.CFI_FLAGS if cfi else frozenset())
        (root/('.'+m.NAME+suffix)).write_text('cmd_test := clang '+' '.join(sorted(flags))+'\n')
    generated = ''.join(f'{{ 0x{crc:08x}, "{name}" }},\n' for name, crc in versions.items())
    module.with_suffix('.mod.c').write_text(generated)
    args = (module, root, source, symvers, runtime)
    result = m.verify(*args)
    assert result['artifact_checks_passed']
    for key in ('stock_binary_equivalence_proven', 'deployment_enabled', 'hardware_tested',
                'runtime_identity_verified', 'availability_proven', 'ownership_acquired', 'boot_ready'):
        assert result[key] is False
    for path, bad in ((root/'.config', config+'# changed\n'),
                      (root/'Module.symvers', stock+'\n'), (runtime, config+'# changed\n'),
                      (release, 'wrong\n'), (module.with_suffix('.c'), 'wrong source\n'),
                      (module.with_suffix('.mod.c'), generated+generated.splitlines()[0]+'\n')):
        before = path.read_bytes(); path.write_text(bad)
        rejected(m.verify, *args); path.write_bytes(before)
print('PASS identity module verifier: synthetic ELF bounds/versions/imports/CRCs, flags, provenance, no deployment/runtime claims')
