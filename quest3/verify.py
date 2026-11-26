#!/usr/bin/env python3
"""Verify actual kernel/module artifacts; never load them on a device."""
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path('/workspace/quest3-build')

class ELF:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        assert self.data[:6] == b'\x7fELF\x02\x01', f'Expected little-endian ELF64: {path}'
        assert struct.unpack_from('<H', self.data, 18)[0] == 183, f'Expected ARM64: {path}'
        off = struct.unpack_from('<Q', self.data, 40)[0]
        size, count, names_index = struct.unpack_from('<HHH', self.data, 58)
        self.headers = [struct.unpack_from('<IIQQQQIIQQ', self.data, off+i*size) for i in range(count)]
        h = self.headers[names_index]
        names = self.data[h[4]:h[4]+h[5]]
        self.sections = {self.string(names, h[0]): h for h in self.headers}

    @staticmethod
    def string(data, offset):
        return data[offset:data.index(b'\0', offset)].decode()

    def section(self, name):
        h = self.sections[name]
        return self.data[h[4]:h[4]+h[5]]

    def symbols(self):
        h = self.sections['.symtab']
        sh = self.headers[h[6]]
        strings = self.data[sh[4]:sh[4]+sh[5]]
        symbols = {}
        for pos in range(h[4], h[4]+h[5], h[9]):
            name, info, other, index, value, size = struct.unpack_from('<IBBHQQ', self.data, pos)
            symbols[self.string(strings, name)] = (index, value, size, info)
        return symbols

def config(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('CONFIG_'):
            key, value = line.split('=', 1)
            values[key] = value
        else:
            match = re.fullmatch(r'# (CONFIG_\w+) is not set', line)
            if match:
                values[match[1]] = 'n'
    return values

cfg = config(ROOT/'out/.config')
device = config(ROOT/'device.config')
required = ['SHADOW_CALL_STACK','LTO_CLANG_FULL','CFI_CLANG','CFI_CLANG_SHADOW','MODVERSIONS','META_SAMPLE_PGO']
assert all(cfg.get('CONFIG_'+key) == 'y' for key in required)
changes = {key: [device[key], cfg[key]] for key in sorted(device.keys() & cfg.keys()) if device[key] != cfg[key]}
assert set(changes) <= {'CONFIG_LOCALVERSION_AUTO', 'CONFIG_PAHOLE_VERSION'}, changes
assert not [(key, value) for key, value in device.items() if value != 'n' and key not in cfg]
release = (ROOT/'out/include/config/kernel.release').read_text().strip()
assert release == '5.10.246-gd7102a837402'
assert (ROOT/'out/arch/arm64/boot/Image').read_bytes()[56:60] == b'ARM\x64'

exports = {}
for line in (ROOT/'out/Module.symvers').read_text().splitlines():
    fields = line.split()
    exports[fields[1]] = int(fields[0], 16)

reference_exports = {}
for line in (ROOT/'inputs/quest3-llvm-config.bOyxO7/Module.symvers').read_text().splitlines():
    fields = line.split()
    reference_exports[fields[1]] = int(fields[0], 16)
export_changes = {name:[reference_exports[name],exports[name]] for name in reference_exports.keys() & exports.keys() if reference_exports[name] != exports[name]}
assert not export_changes, export_changes
assert reference_exports.keys() == exports.keys(), 'Exported symbol set differs from supplied final build'

module_results = {}
for name in ['quest_kexec', 'marker_read', 'usb_log']:
    path = ROOT/'module'/f'{name}.ko'
    elf = ELF(path)
    versions = elf.section('__versions')
    assert len(versions) % 64 == 0
    for pos in range(0, len(versions), 64):
        crc = struct.unpack_from('<Q', versions, pos)[0]
        symbol = ELF.string(versions, pos+8)
        assert exports.get(symbol) == crc, (name, symbol, hex(crc), exports.get(symbol))
    symbols = elf.symbols()
    assert symbols['__cfi_check'][0] != 0, f'CFI check missing: {name}'
    assert any(value.startswith(b'vermagic='+release.encode()+b' ') for value in elf.section('.modinfo').split(b'\0'))
    command_name = {'quest_kexec':'loader', 'marker_read':'marker_read', 'usb_log':'usb_log'}[name]
    command = (ROOT/'module'/f'.{command_name}.o.cmd').read_text().splitlines()[0]
    for flag in ['--target=aarch64-linux-gnu', '-flto', '-fsanitize=cfi', '-fsanitize=shadow-call-stack', '-ffixed-x18']:
        assert flag in command, (name, flag)
    module_results[name] = {'crc_matches':len(versions)//64, 'crc_mismatches':0, 'cfi_check':True, 'scs_compile_flag':True}

kernel = ELF(ROOT/'out/vmlinux')
btf = kernel.section('.BTF')
magic, version, flags, header, type_off, type_len, string_off, string_len = struct.unpack_from('<HBBIIIII', btf)
assert magic == 0xeb9f and version == 1
strings = btf[header+string_off:header+string_off+string_len]
pos, end, type_id = header+type_off, header+type_off+type_len, 1
vfs_id = None
function_names = {}
fixed_extra = {1:4, 2:0, 3:12, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0, 14:4, 16:0, 17:4, 18:0}
while pos < end:
    name, info, size_type = struct.unpack_from('<III', btf, pos)
    kind, vlen = (info >> 24) & 31, info & 65535
    if kind == 12:
        function_names[type_id] = ELF.string(strings, name)
        if function_names[type_id] == 'vfs_truncate':
            vfs_id = type_id
    extra = fixed_extra.get(kind)
    if extra is None:
        extra = vlen * {4:12, 5:12, 6:8, 13:8, 15:12, 19:12}[kind]
    pos += 12 + extra
    type_id += 1
assert pos == end and vfs_id is not None, 'vfs_truncate missing in BTF'
symbols = kernel.symbols()
index, value, size, info = symbols['__BTF_ID__set__btf_allowlist_d_path']
h = kernel.headers[index]
offset = h[4] + value - h[3]
count = struct.unpack_from('<I', kernel.data, offset)[0]
assert count > 0 and size == (count+1)*4
ids = list(struct.unpack_from('<'+'I'*count, kernel.data, offset+4))
assert ids == sorted(ids), 'BTF allowlist is not sorted'
# resolve_btfids/main.c sets_patch() sorts the array in place. Individual
# __BTF_ID__func__ labels retain their original offsets and no longer label
# the corresponding function's value after sorting. Check the whole set.
expected_names = []
for name, (idx, addr, _, _) in symbols.items():
    if idx == index and value+4 <= addr < value+(count+1)*4 and name.startswith('__BTF_ID__func__'):
        expected_names.append(name[len('__BTF_ID__func__'):].rsplit('__',1)[0])
actual_names = [function_names.get(type_id) for type_id in ids]
assert len(expected_names) == count and None not in actual_names
assert sorted(actual_names) == sorted(expected_names), (expected_names, actual_names)
assert vfs_id in ids, (vfs_id, ids)

for log in ['kernel-build.log','module-build.log']:
    text = (ROOT/log).read_text()
    assert not re.search(r'FAILED unresolved symbol|FAILED to generate BTF|^.*make(?:\[\d+\])?: \*\*\*', text, re.M), log
assert 'BTFIDS  vmlinux' in (ROOT/'kernel-build.log').read_text()
subprocess.run(['git','-C',str(ROOT/'kernel'),'diff','--exit-code'], check=True, stdout=subprocess.DEVNULL)

result = {
    'release': release,
    'kernel_commit': subprocess.check_output(['git','-C',str(ROOT/'kernel'),'rev-parse','HEAD'],text=True).strip(),
    'config_matches_device_except': changes,
    'security_options': {key:cfg['CONFIG_'+key] for key in required},
    'vfs_truncate_btf_id':vfs_id,
    'vfs_truncate_present_in_allowlist':True,
    'd_path_allowlist_btf_ids':ids,
    'd_path_allowlist_functions':actual_names,
    'reference_kernel_export_crc_matches':len(reference_exports),
    'reference_kernel_export_crc_mismatches':len(export_changes),
    'modules':module_results,
    'nonfatal_build_warnings': [line for log in ['kernel-build.log','module-build.log'] for line in (ROOT/log).read_text().splitlines() if 'warning:' in line],
    'runtime_tested_on_device':False,
}
(ROOT/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
