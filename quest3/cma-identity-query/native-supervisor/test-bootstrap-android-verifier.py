#!/usr/bin/env python3
"""Synthetic bootstrap report rejection cases; no NDK or Android execution."""
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('bootstrap_android_verifier',Path(__file__).with_name('verify-bootstrap-android.py'))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def denied(function,*args):
    try: function(*args)
    except ValueError: pass
    else: raise AssertionError('unsafe bootstrap artifact/report accepted')


assembly='''00000000000005d8 <main>:
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
ir='define hidden i32 @'+m.CORE+'(ptr %r) !type !1'
for variant in sorted(m.VARIANTS):
    keep=variant=='core-linkcheck-disarmed'
    flags=sorted(m.base.FLAGS)+([m.KEEP] if keep else [])
    symbols='0 t main\n1 T _start\n'+('2 t '+m.CORE+'\n' if keep else '')
    symbols+=''.join(' U '+n+'\n' for n in sorted(m.IMPORTS if keep else {'__libc_init','write'}))
    result=m.check_reports(flags,symbols,assembly,ir,variant)
    assert result['main_disassembly_write_then_return_77']
    assert result['core_retained_for_linkcheck']==keep and not result['cfi_runtime_enforcement_validated']
    assert m.check_reports(flags,symbols,assembly,ir.replace('hidden i32','hidden range(i32 0, 78) i32'),variant)
    for flag in m.base.FLAGS:
        denied(m.check_reports,[f for f in flags if f!=flag],symbols,assembly,ir,variant)
    for bad in ('-DQ3_BOOTSTRAP_HOST_TEST','-DQ3_SUPERVISOR_HOST_TEST','-flto=thin',
                '-fno-sanitize=cfi','-fsanitize=shadow-call-stack','-fsanitize-recover=cfi'):
        denied(m.check_reports,flags+[bad],symbols,assembly,ir,variant)
    denied(m.check_reports,flags,symbols+' U system\n',assembly,ir,variant)
    denied(m.check_reports,flags,symbols.replace('main','enabled_main'),assembly,ir,variant)
    for changed in (assembly.replace('write@plt',m.CORE),assembly.replace('#0x4d','#0x0'),
                    assembly.replace('nop','blr'),assembly.replace('ret','b')):
        denied(m.check_reports,flags,symbols,changed,ir,variant)
    denied(m.check_reports,flags,symbols,assembly,'',variant)
    denied(m.check_reports,flags,symbols,assembly,ir.replace(' !type !1','')+'\n!type !1',variant)
    denied(m.check_reports,flags,symbols,assembly,ir,'live')
    denied(m.check_reports,[f for f in flags if f!=m.KEEP] if keep else flags+[m.KEEP],symbols,assembly,ir,variant)
    versions='File: libc.so\n'+''.join('Name: '+n+'\n' for n in (['LIBC','LIBC_N'] if keep else ['LIBC']))
    assert m.check_versions(versions,variant)
    for changed in (versions+'Name: LIBC_P\n',versions+'Name: LIBC\n',versions.replace('libc.so','libc.so.6')):
        denied(m.check_versions,changed,variant)
for marker in (b'--host-bootstrap',b'Q3_BOOTSTRAP_FAULT',b'Q3_BOOTSTRAP_PAUSE'):
    denied(m.markers,b'prefix'+marker+b'suffix')
m.markers(b'disarmed metadata-only bootstrap')
print('PASS bootstrap Android verifier: disarmed main, exact imports/versions, flags, CFI metadata and test-CLI rejection; no Android execution')
