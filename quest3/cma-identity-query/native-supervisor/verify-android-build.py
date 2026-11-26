#!/usr/bin/env python3
"""Offline Android artifact/recorded LLVM report checks. Never executes Android code."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

MESSAGE = b'Disarmed native prototype: no Android/device dispatcher enabled.\n'
CORE_IMPORTS = frozenset(('__errno __libc_init __open_2 __openat_2 __read_chk __stack_chk_fail '
                          '__vsnprintf_chk __write_chk _exit calloc close closedir dirfd dup2 fcntl '
                          'fdopendir fexecve flock fork free fstat fstatat fsync geteuid linkat lseek '
                          'lstat malloc memcmp memcpy memset openat opendir pipe2 poll pread read '
                          'readdir sigaction sigemptyset sigprocmask strcmp strlen strspn strtol unlinkat '
                          'waitpid write').split())
FLAGS = frozenset(('--target=aarch64-linux-android28', '-flto=full', '-fvisibility=hidden',
                    '-fsanitize=cfi', '-fsanitize-trap=cfi', '-fstack-protector-strong',
                    '-D_FORTIFY_SOURCE=2', '-ffixed-x18', '-fPIE', '-pie',
                    '-Wl,-z,relro,-z,now,-z,noexecstack',
                    '-Wl,--no-undefined,--fatal-warnings,--gc-sections'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect_elf(blob):
    def part(offset, size):
        if offset < 0 or size < 0 or offset+size > len(blob):
            raise ValueError('ELF range outside file')
        return blob[offset:offset+size]

    if (len(blob) < 64 or blob[:7] != b'\x7fELF\x02\x01\x01' or
            struct.unpack_from('<HHI', blob, 16) != (3, 183, 1)):
        raise ValueError('not ELF64 little-endian AArch64 ET_DYN')
    entry, offset = struct.unpack_from('<QQ', blob, 24)
    size, count = struct.unpack_from('<HH', blob, 54)
    if size != 56 or not count or offset < 64:
        raise ValueError('invalid program header table')
    part(offset, size*count)
    headers = [struct.unpack_from('<IIQQQQQQ', blob, offset+i*size) for i in range(count)]
    for header in headers:
        part(header[2], header[5])
        if header[5] > header[6]:
            raise ValueError('ELF filesz exceeds memsz')
    loads = [h for h in headers if h[0] == 1]
    if not loads or any(h[1] & 3 == 3 for h in loads):
        raise ValueError('missing load segments or writable executable mapping')
    if not any(h[1] & 1 and h[3] <= entry < h[3]+h[5] for h in loads):
        raise ValueError('entry is not in executable file-backed mapping')
    for header in loads:
        alignment = header[7]
        if (header[3]+header[6] > 1 << 64 or alignment < 4096 or alignment & (alignment-1) or
                header[2] % alignment != header[3] % alignment):
            raise ValueError('unsupported load alignment')

    def one(kind):
        matched = [h for h in headers if h[0] == kind]
        if len(matched) != 1:
            raise ValueError('required program header missing/duplicated: ' + hex(kind))
        return matched[0]

    interp = one(3)
    if part(interp[2], interp[5]) != b'/system/bin/linker64\0':
        raise ValueError('unexpected Android interpreter')
    if one(0x6474e551)[1] & 1 or not one(0x6474e552)[6]:
        raise ValueError('executable stack or empty RELRO')
    dynamic = one(2)
    if dynamic[5] % 16:
        raise ValueError('invalid dynamic table size')
    tags = {}
    terminated = False
    for index in range(0, dynamic[5], 16):
        tag, value = struct.unpack('<QQ', part(dynamic[2]+index, 16))
        if not tag:
            terminated = True
            break
        tags.setdefault(tag, []).append(value)
    if not terminated or any(tag in tags for tag in (15, 22, 29)):
        raise ValueError('unterminated dynamic table, TEXTREL or search path override')

    def unique(tag):
        values = tags.get(tag, [])
        if len(values) != 1:
            raise ValueError('missing/duplicate dynamic tag: ' + str(tag))
        return values[0]

    if not unique(0x6ffffffb) & 0x08000000 or not (unique(0x6ffffffb) & 1 or unique(30) & 8):
        raise ValueError('PIE/NOW flags absent')
    if 30 in tags and unique(30) & 4:
        raise ValueError('DF_TEXTREL flag is not allowed')
    address, length = unique(5), unique(10)
    mapped = [h for h in loads if h[3] <= address and address+length <= h[3]+h[5]]
    if len(mapped) != 1:
        raise ValueError('invalid dynamic string mapping')
    strings = part(mapped[0][2]+address-mapped[0][3], length)
    needed = []
    for start in tags.get(1, []):
        end = strings.find(b'\0', start)
        if not 0 <= start < len(strings) or end < 0:
            raise ValueError('invalid dependency string')
        needed.append(strings[start:end].decode('ascii'))
    if sorted(needed) != ['libc.so', 'libdl.so']:
        raise ValueError('unexpected dependencies, not the reviewed Bionic pair')
    notes = []
    for header in headers:
        if header[0] != 4:
            continue
        data = part(header[2], header[5]); position = 0
        while position < len(data):
            if position+12 > len(data):
                raise ValueError('truncated ELF note')
            namesz, descsz, kind = struct.unpack_from('<III', data, position)
            position += 12
            name = data[position:position+namesz]; position += (namesz+3) & ~3
            desc = data[position:position+descsz]; position += (descsz+3) & ~3
            if position > len(data) or len(name) != namesz or len(desc) != descsz:
                raise ValueError('truncated ELF note payload')
            if name == b'Android\0' and kind == 1:
                if descsz != 132:
                    raise ValueError('unexpected Android ident layout')
                notes.append((struct.unpack_from('<I', desc)[0], desc[4:68].split(b'\0')[0].decode(),
                              desc[68:132].split(b'\0')[0].decode()))
    if notes != [(28, 'r30', '16248370')]:
        raise ValueError('Android API/NDK ident mismatch')
    if MESSAGE not in blob or b'--host-fixture' in blob or b'Q3_NATIVE_FAULT' in blob:
        raise ValueError('missing disarmed message or test dispatcher markers present')
    return dict(elf_machine='AArch64', elf_type='ET_DYN', android_api_note=28,
                ndk_ident='r30/16248370', interpreter='/system/bin/linker64',
                needed=sorted(needed), pie=True, bind_now=True, relro_present=True,
                executable_stack=False, writable_executable_load=False, textrel=False,
                load_alignments_bytes=sorted({h[7] for h in loads}),
                runtime_compatibility_validated=False)


def check_reports(command, symbols, disassembly, ir, variant):
    if variant not in ('disarmed', 'core-linkcheck-disarmed') or not FLAGS <= set(command):
        raise ValueError('variant or required compile flags mismatch')
    if any(('Q3_SUPERVISOR_HOST_TEST' in flag or flag.startswith((
            '-fno-sanitize=', '-fsanitize-recover=', '-fno-lto', '-fno-stack-protector',
            '-fsanitize=shadow-call-stack')) or flag == '-flto=thin') for flag in command):
        raise ValueError('test dispatcher, conflicting protections or unreviewed SCS runtime')
    keep = '-Wl,--undefined=q3_supervise_fixture' in command
    if keep != (variant == 'core-linkcheck-disarmed'):
        raise ValueError('core linkcheck retention flag mismatch')
    defined, undefined = set(), set()
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == 'U':
            undefined.add(fields[1])
        elif len(fields) == 3 and re.fullmatch(r'[0-9a-f]+', fields[0]):
            defined.add(fields[2])
    if 'main' not in defined or '_start' not in defined or 'host_signal_fd' in defined:
        raise ValueError('entry or test-only symbols inconsistent')
    if ('q3_supervise_fixture' in defined) != keep or undefined != (CORE_IMPORTS if keep else {'__libc_init', 'write'}):
        raise ValueError('retained core/imports differ from reviewed profile')
    match = re.search(r'^[0-9a-f]+ <main>:\n(.*?)(?:\n\n|\Z)', disassembly, re.M | re.S)
    if not match:
        raise ValueError('main disassembly missing')
    instructions = []
    for line in match[1].splitlines():
        parsed = re.fullmatch(r'\s*[0-9a-f]+:\s+[0-9a-f]{8}\s+(\w+)\s*(.*?)\s*', line)
        if not parsed:
            raise ValueError('unexpected main disassembly format')
        instructions.append((parsed[1], parsed[2].split('//')[0].strip()))
    calls = [i for i, (op, _) in enumerate(instructions) if op == 'bl']
    if len(calls) != 1 or '<write@plt>' not in instructions[calls[0]][1]:
        raise ValueError('main is not the disarmed write-only entry')
    after = instructions[calls[0]+1:]
    if (len(after) != 3 or after[0] != ('mov', 'w0, #0x4d') or
            after[1] != ('ldp', 'x29, x30, [sp], #0x10') or after[2] != ('ret', '')):
        raise ValueError('main does not directly return 77 after write')
    for op, operands in instructions[:calls[0]]:
        if op not in {'stp', 'mov', 'nop', 'adr', 'adrp', 'add'} or op == 'add' and not operands.startswith('x1,'):
            raise ValueError('unexpected instructions/control flow before disarmed write')
    if 'define hidden i32 @q3_supervise_fixture' not in ir or '!type' not in ir:
        raise ValueError('core/CFI type metadata missing from recorded prelink IR')
    return dict(main_disassembly_write_then_return_77=True, core_retained_for_linkcheck=keep,
                recorded_undefined_symbols=sorted(undefined), recorded_compile_flags_checked=sorted(FLAGS),
                prelink_ir_core_and_cfi_type_metadata_present=True,
                cfi_runtime_enforcement_validated=False, scs_enabled=False)


def check_versions(text, variant):
    names = re.findall(r'\bName: (\S+)', text)
    expected = {'LIBC', 'LIBC_N', 'LIBC_P'} if variant == 'core-linkcheck-disarmed' else {'LIBC'}
    if (len(names) != len(expected) or set(names) != expected or
            re.findall(r'\bFile: (\S+)', text) != ['libc.so'] or 'GLIBC' in text):
        raise ValueError('unexpected Bionic symbol versions')
    return sorted(expected)


def verify(out, archive):
    job = json.loads((archive/'result.json').read_text())
    intent = json.loads((archive/'intent.json').read_text())
    if len(job['commands']) != 2:
        raise ValueError('exactly two build profiles required')
    artifacts = {}
    for record in job['commands']:
        variant = record['variant']; binary = out/variant/'supervisor'
        blob = binary.read_bytes()
        if record['build_exit_code'] != 0 or digest(blob) != record['binary_sha256']:
            raise ValueError('build result/hash inconsistent')
        item = inspect_elf(blob)
        item.update(check_reports(record['argv'], (archive/(variant+'.symbols.txt')).read_text(),
                                  (archive/(variant+'.disassembly.txt')).read_text(),
                                  (archive/(variant+'.ll')).read_text(), variant))
        item['recorded_bionic_symbol_versions'] = check_versions((archive/(variant+'.versions.txt')).read_text(), variant)
        for name in ('supervisor.c', 'sha256.h'):
            if (digest((out/'source'/name).read_bytes()) != intent['source_sha256'][name] or
                    digest(Path(__file__).with_name(name).read_bytes()) != intent['source_sha256'][name]):
                raise ValueError('source provenance mismatch')
        if (out/variant/'supervisor.o').read_bytes()[:4] != b'BC\xc0\xde':
            raise ValueError('primary object is not LLVM bitcode')
        item.update(bytes=len(blob), sha256=digest(blob))
        artifacts[variant] = item
    if set(artifacts) != {'disarmed', 'core-linkcheck-disarmed'}:
        raise ValueError('both disarmed build profiles required')
    return dict(scope='offline ELF plus recorded LLVM reports/flags, not Android execution',
                artifact_checks_passed=True, artifacts=artifacts, minimum_android_api=28,
                ndk_revision='30.0.16248370', source_sha256=intent['source_sha256'],
                android_runtime_tested=False, device_api_validated=False,
                production_dispatcher_enabled=False, controller_integrated=False,
                deployment_enabled=False, device_operation_performed=False,
                kernel_cfi_scs_lto_settings_changed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    try:
        value = verify(args.out, args.archive)
    except (OSError, ValueError, KeyError, struct.error) as error:
        parser.exit(2, str(error)+'\n')
    print(json.dumps(value, indent=2))
