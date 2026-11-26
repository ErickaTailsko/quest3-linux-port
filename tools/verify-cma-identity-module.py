#!/usr/bin/env python3
"""Offline verification of the identity-only stock module; never enables deployment."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct

NAME = 'q3_cma_identity'
VERMAGIC = '5.10.246-gd7102a837402 SMP preempt mod_unload modversions aarch64'
CONFIG_HASH = 'e45b01529aa554bab274e7362b1a052517016314270cdd30adfa20413ea0faed'
STOCK_CONFIG_HASH = 'fa0342f1b1dc12d2a723ecb1e390877b31f729480ad8328a89c1b5ae6b1f9a99'
SYMVERS_HASH = 'c250004c0e4ac84ca2d83797109f08d7adf31b9c76450dd5a4fcc996b0a48078'
IMPORTS = frozenset(('module_layout', '__stack_chk_fail', '__ubsan_handle_cfi_check_fail_abort',
                     'dma_contiguous_default_area', 'cma_get_name', 'kernel_kobj',
                     'param_ops_string', 'param_ops_bool', 'sysfs_remove_file_ns', 'sysfs_emit',
                     'sysfs_create_file_ns', 'of_find_property', 'of_find_node_opts_by_path',
                     'strncmp', 'of_reserved_mem_lookup', 'of_property_read_u64',
                     'of_device_is_compatible', 'of_device_is_available', 'kobject_put',
                     'kobject_create_and_add', 'snprintf', 'of_machine_is_compatible', 'strlen'))
BASE_FLAGS = frozenset(('--target=aarch64-linux-gnu', '-ffixed-x18',
                        '-fsanitize=shadow-call-stack', '-flto', '-fstack-protector-strong'))
CFI_FLAGS = frozenset(('-fsanitize=cfi', '-fsanitize-cfi-cross-dso'))
REQUIRED = ('ARM64', 'ARM64_4K_PAGES', 'CMA', 'DMA_CMA', 'OF_RESERVED_MEM',
            'CFI_CLANG', 'CFI_CLANG_SHADOW', 'SHADOW_CALL_STACK', 'LTO_CLANG_FULL',
            'MODVERSIONS', 'STACKPROTECTOR_STRONG', 'MODULE_UNLOAD')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_config(text):
    lines = set(text.splitlines())
    for key in REQUIRED:
        if 'CONFIG_' + key + '=y' not in lines:
            raise ValueError('required stock setting missing: ' + key)
    for key in ('CFI_PERMISSIVE', 'LTO_CLANG_THIN', 'OF_DYNAMIC', 'OF_OVERLAY'):
        if 'CONFIG_' + key + '=y' in lines:
            raise ValueError('unsupported setting: ' + key)


def check_command(text, cfi):
    first = text.splitlines()[0] if text.splitlines() else ''
    if ':=' not in first:
        raise ValueError('missing recorded compile command')
    tokens = shlex.split(first.split(':=', 1)[1])
    flags = set(tokens)
    required = BASE_FLAGS | (CFI_FLAGS if cfi else frozenset())
    if not required <= flags:
        raise ValueError('missing compile protection: ' + ','.join(sorted(required-flags)))
    if any(t.startswith(('-fno-sanitize=', '-fsanitize-recover=', '-fno-stack-protector',
                         '-fno-sanitize-cfi-cross-dso', '-fno-lto', '-ffixed-x18=', '-flto=')) for t in tokens):
        raise ValueError('conflicting sanitizer/LTO/stack flags')
    return sorted(required)


def cstring(data, offset):
    if not 0 <= offset < len(data):
        raise ValueError('string offset outside table')
    end = data.find(b'\0', offset)
    if end < 0:
        raise ValueError('unterminated ELF string')
    return data[offset:end].decode('ascii')


def elf_sections(blob):
    if (len(blob) < 64 or blob[:7] != b'\x7fELF\x02\x01\x01' or
            struct.unpack_from('<HHI', blob, 16) != (1, 183, 1)):
        raise ValueError('not a relocatable ELF64 little-endian AArch64 module')
    offset = struct.unpack_from('<Q', blob, 40)[0]
    header_size, entry_size, count, names_index = struct.unpack_from('<HxxxxHHH', blob, 52)
    if header_size != 64 or entry_size != 64 or not 0 < names_index < count:
        raise ValueError('unsupported ELF section table')
    if offset < 64 or offset + count*64 > len(blob):
        raise ValueError('truncated ELF section table')
    headers = [struct.unpack_from('<IIQQQQIIQQ', blob, offset+i*64) for i in range(count)]

    def contents(header):
        if header[1] == 8:  # NOBITS does not occupy file bytes.
            return b''
        start, size = header[4:6]
        if start + size > len(blob):
            raise ValueError('ELF section outside file')
        return blob[start:start+size]

    if headers[names_index][1] != 3:
        raise ValueError('invalid section-name table')
    names = contents(headers[names_index])
    sections = {}
    for index, header in enumerate(headers):
        name = cstring(names, header[0])
        data = contents(header)
        if index and (not name or name in sections):
            raise ValueError('empty/duplicate section name')
        sections[name] = (header, data)
    return headers, sections


def inspect_module(blob, stock_symvers):
    headers, sections = elf_sections(blob)
    for name in ('.modinfo', '__versions', '.symtab'):
        if name not in sections:
            raise ValueError('required ELF section missing: ' + name)
    info = {}
    for item in sections['.modinfo'][1].split(b'\0'):
        if not item:
            continue
        key, separator, value = item.decode('ascii').partition('=')
        if not separator:
            raise ValueError('malformed module metadata')
        info.setdefault(key, []).append(value)
    for key, expected in (('vermagic', VERMAGIC), ('name', NAME), ('license', 'GPL'), ('depends', '')):
        if info.get(key) != [expected]:
            raise ValueError('unexpected module metadata: ' + key)
    if set(info.get('parmtype', [])) != {'inspect:bool', 'attempt:string'}:
        raise ValueError('unexpected opt-in/token parameter types')
    versions = sections['__versions'][1]
    if not versions or len(versions) % 64:
        raise ValueError('invalid ARM64 modversion record size')
    imported = {}
    for offset in range(0, len(versions), 64):
        crc = struct.unpack_from('<Q', versions, offset)[0]
        name = cstring(versions[offset+8:offset+64], 0)
        if not name or name in imported or crc > 0xffffffff:
            raise ValueError('invalid/duplicate modversion record')
        imported[name] = crc
    if set(imported) != IMPORTS:
        raise ValueError('module imports differ from identity-only allowlist')
    exports = {}
    for line in stock_symvers.splitlines():
        fields = line.split()
        if len(fields) < 4:
            raise ValueError('invalid stock symvers row')
        crc, name, provider = int(fields[0], 16), fields[1], fields[2]
        if name in exports:
            raise ValueError('duplicate stock export')
        exports[name] = (crc, provider)
    for name, crc in imported.items():
        if exports.get(name) != (crc, 'vmlinux'):
            raise ValueError('stock CRC/provider mismatch: ' + name)
    sym_header, symbols = sections['.symtab']
    link = sym_header[6]
    if sym_header[1] != 2 or sym_header[9] != 24 or len(symbols) % 24 or not 0 < link < len(headers):
        raise ValueError('invalid ELF symbol table')
    strings_header = headers[link]
    if strings_header[1] != 3:
        raise ValueError('invalid ELF symbol string table')
    strings = blob[strings_header[4]:strings_header[4]+strings_header[5]]
    undefined, defined = set(), set()
    for offset in range(0, len(symbols), 24):
        name_offset, _, _, section, _, _ = struct.unpack_from('<IBBHQQ', symbols, offset)
        name = cstring(strings, name_offset)
        if name:
            (defined if section else undefined).add(name)
    if undefined != IMPORTS - {'module_layout'}:
        raise ValueError('ELF undefined symbols differ from checked versions')
    for symbol in ('__cfi_check', 'init_module', 'cleanup_module', 'report_show',
                   '__cfi_jt_init_module', '__cfi_jt_cleanup_module', '__param_inspect', '__param_attempt'):
        if symbol not in defined:
            raise ValueError('required linked symbol missing: ' + symbol)
    return dict(vermagic=VERMAGIC, elf_machine='AArch64', elf_type='REL',
                imported_versioned_symbols={name: f'0x{crc:08x}' for name, crc in sorted(imported.items())},
                all_import_crcs_match_supplied_stock=True, undefined_symbols_match_versions=True,
                identity_only_import_allowlist_passed=True, cfi_check_present=True)


def verify(module, out, source, symvers, stock_config):
    config, supplied, runtime = (out/'.config').read_bytes(), symvers.read_bytes(), stock_config.read_bytes()
    if (digest(config) != CONFIG_HASH or digest(supplied) != SYMVERS_HASH or
            digest(runtime) != STOCK_CONFIG_HASH or (out/'Module.symvers').read_bytes() != supplied):
        raise ValueError('stock/prepared config or supplied symvers provenance mismatch')
    check_config(config.decode())
    check_config(runtime.decode())
    if (out/'include/config/kernel.release').read_text().strip() != VERMAGIC.split()[0]:
        raise ValueError('unexpected prepared release')
    if module.with_suffix('.c').read_bytes() != source.read_bytes():
        raise ValueError('built source copy differs from reviewed project source')
    commands = {}
    for suffix, cfi in (('.o.cmd', True), ('.mod.o.cmd', False)):
        path = module.parent/('.' + NAME + suffix)
        commands[suffix] = check_command(path.read_text(), cfi)
    blob = module.read_bytes()
    result = inspect_module(blob, supplied.decode())
    generated = module.with_suffix('.mod.c').read_text()
    records = re.findall(r'\{\s*(0x[0-9a-fA-F]+),\s*"([^"]+)"\s*\}', generated)
    mod_versions = {name: f'0x{int(crc,16):08x}' for crc, name in records}
    if len(records) != len(mod_versions) or mod_versions != result['imported_versioned_symbols']:
        raise ValueError('generated mod.c versions differ from ELF')
    result.update(artifact_checks_passed=True, module_sha256=digest(blob), module_bytes=len(blob),
                  source_sha256=digest(source.read_bytes()), prepared_config_sha256=digest(config),
                  stock_runtime_config_sha256=digest(runtime), supplied_symvers_sha256=digest(supplied),
                  checked_compile_flags=commands, metadata_translation_unit_cfi_exempt=True,
                  struct_reserved_mem_size=56, struct_reserved_mem_field_offsets=dict(ops=24,base=32,size=40,priv=48),
                  layout_asserts_compiled_against_public_headers_not_stock_binary=True,
                  scope='artifact/recorded-flags consistency, not stock binary equivalence or runtime safety',
                  stock_binary_equivalence_proven=False, deployment_enabled=False,
                  hardware_tested=False, runtime_identity_verified=False,
                  availability_proven=False, ownership_acquired=False, boot_ready=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('module', 'out', 'source', 'symvers', 'stock-config'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.module, args.out, args.source, args.symvers, args.stock_config)
    except (OSError, ValueError, struct.error) as error:
        parser.exit(2, str(error)+'\n')
    print(json.dumps(result, indent=2))
