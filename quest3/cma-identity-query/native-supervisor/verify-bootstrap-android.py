#!/usr/bin/env python3
"""Offline bootstrap ELF/recorded-report checks only; never executes Android code."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('supervisor_android_verifier', Path(__file__).with_name('verify-android-build.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
CORE = 'q3_bootstrap_metadata_reference'
KEEP = '-Wl,--undefined='+CORE
IMPORTS = frozenset(('__errno __libc_init __openat_2 __stack_chk_fail __strlen_chk '
                     '__vsnprintf_chk __write_chk close closedir fdopendir flock fstat fstatat '
                     'fsync geteuid linkat lstat memcpy memset mkdirat openat readdir sigaction '
                     'sigemptyset strcmp strlen unlinkat write').split())
VARIANTS = {'disarmed', 'core-linkcheck-disarmed'}


def markers(blob):
    for marker in (b'--host-bootstrap', b'Q3_BOOTSTRAP_FAULT', b'Q3_BOOTSTRAP_PAUSE'):
        if marker in blob:
            raise ValueError('host bootstrap test marker in Android artifact')


def check_reports(command, symbols, disassembly, ir, variant):
    if variant not in VARIANTS or not base.FLAGS <= set(command):
        raise ValueError('bootstrap variant/required flags mismatch')
    if any(('Q3_BOOTSTRAP_HOST_TEST' in flag or 'Q3_SUPERVISOR_HOST_TEST' in flag or
            flag.startswith(('-fno-sanitize=', '-fsanitize-recover=', '-fno-lto',
                             '-fno-stack-protector', '-fsanitize=shadow-call-stack')) or
            flag == '-flto=thin') for flag in command):
        raise ValueError('test CLI/conflicting hardening/unreviewed SCS runtime')
    keep = variant == 'core-linkcheck-disarmed'
    if (KEEP in command) != keep:
        raise ValueError('bootstrap core retention flag mismatch')
    defined, undefined = set(), set()
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields)==2 and fields[0]=='U': undefined.add(fields[1])
        elif len(fields)==3 and re.fullmatch('[0-9a-f]+',fields[0]): defined.add(fields[2])
    if (not {'main','_start'} <= defined or (CORE in defined) != keep or
            undefined != (IMPORTS if keep else {'__libc_init','write'})):
        raise ValueError('bootstrap symbols/imports mismatch')
    match = re.search(r'^[0-9a-f]+ <main>:\n(.*?)(?:\n\n|\Z)',disassembly,re.M|re.S)
    if not match: raise ValueError('main disassembly missing')
    instructions = []
    for line in match[1].splitlines():
        parsed = re.fullmatch(r'\s*[0-9a-f]+:\s+[0-9a-f]{8}\s+(\w+)\s*(.*?)\s*',line)
        if not parsed: raise ValueError('unexpected main instruction format')
        instructions.append((parsed[1],parsed[2].split('//')[0].strip()))
    calls = [i for i,(op,_) in enumerate(instructions) if op=='bl']
    if len(calls)!=1 or '<write@plt>' not in instructions[calls[0]][1]:
        raise ValueError('main must only call write')
    if instructions[calls[0]+1:] != [('mov','w0, #0x4d'),('ldp','x29, x30, [sp], #0x10'),('ret','')]:
        raise ValueError('main must directly return 77')
    for op, operands in instructions[:calls[0]]:
        if op not in {'stp','mov','nop','adr','adrp','add'} or op=='add' and not operands.startswith('x1,'):
            raise ValueError('unexpected control flow before write')
    if not re.search(r'^define hidden (?:range\(i32 0, 78\) )?i32 @'+CORE+r'\([^\n]* !type ![0-9]+',ir,re.M):
        raise ValueError('bootstrap prelink core/CFI metadata missing')
    return dict(main_disassembly_write_then_return_77=True, core_retained_for_linkcheck=keep,
                recorded_undefined_symbols=sorted(undefined), recorded_compile_flags_checked=sorted(base.FLAGS),
                prelink_ir_core_and_cfi_type_metadata_present=True,
                cfi_runtime_enforcement_validated=False, scs_enabled=False)


def check_versions(text, variant):
    if variant not in VARIANTS: raise ValueError('unknown bootstrap variant')
    expected = {'LIBC','LIBC_N'} if variant=='core-linkcheck-disarmed' else {'LIBC'}
    names = re.findall(r'\bName: (\S+)',text)
    if (len(names)!=len(expected) or set(names)!=expected or
            re.findall(r'\bFile: (\S+)',text)!=['libc.so'] or 'GLIBC' in text):
        raise ValueError('bootstrap Bionic versions mismatch')
    return sorted(expected)


def verify(out, archive):
    job = json.loads((archive/'result.json').read_text())
    intent = json.loads((archive/'intent.json').read_text())
    if (len(job['commands'])!=2 or {r['variant'] for r in job['commands']}!=VARIANTS or
            job['android_binaries_executed'] is not False or job['device_operation_performed'] is not False or
            job['deployment_enabled'] is not False or intent['ndk_revision']!='30.0.16248370' or
            set(intent['source_sha256'])!={'bootstrap.c','sha256.h'}):
        raise ValueError('offline build profile/provenance mismatch')
    for name, expected in intent['source_sha256'].items():
        for path in (out/'source'/name, Path(__file__).with_name(name)):
            if base.digest(path.read_bytes())!=expected: raise ValueError('bootstrap source hash mismatch')
    artifacts = {}
    for record in job['commands']:
        variant = record['variant']; binary = out/variant/'bootstrap'; blob = binary.read_bytes()
        if (record['build_exit_code']!=0 or base.digest(blob)!=record['binary_sha256'] or
                len(blob)!=record['binary_bytes']):
            raise ValueError('bootstrap artifact/hash mismatch')
        markers(blob)
        item = base.inspect_elf(blob)
        item.update(check_reports(record['argv'], (archive/(variant+'.symbols.txt')).read_text(),
                                  (archive/(variant+'.disassembly.txt')).read_text(),
                                  (archive/(variant+'.ll')).read_text(),variant))
        item['recorded_bionic_symbol_versions'] = check_versions((archive/(variant+'.versions.txt')).read_text(),variant)
        if (out/variant/'bootstrap.o').read_bytes()[:4]!=b'BC\xc0\xde':
            raise ValueError('bootstrap primary object must be LLVM bitcode')
        item.update(bytes=len(blob),sha256=base.digest(blob))
        artifacts[variant]=item
    return dict(scope='offline bootstrap ELF and recorded LLVM reports; not runtime validation',
                artifact_checks_passed=True,artifacts=artifacts,source_sha256=intent['source_sha256'],
                minimum_android_api=28,ndk_revision='30.0.16248370',android_runtime_tested=False,
                device_api_validated=False,production_dispatcher_enabled=False,pin_import_permitted=False,
                admission_enabled=False,controller_integrated=False,deployment_enabled=False,
                device_operation_performed=False,kernel_cfi_scs_lto_settings_changed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    args=parser.parse_args()
    try: value=verify(args.out,args.archive)
    except (OSError,ValueError,KeyError,TypeError) as error: parser.exit(2,str(error)+'\n')
    print(json.dumps(value,indent=2))
