#!/usr/bin/env python3
"""Verify the experimental kernel separately from stock-compatible artifacts."""
from pathlib import Path
import contextlib, io, json, re, runpy, struct, subprocess
r=Path(__file__).resolve().parent
with contextlib.redirect_stdout(io.StringIO()):
    baseline=runpy.run_path(str(r/'verify.py'))
ELF=baseline['ELF']; config=baseline['config']; n=r/'native-kexec-probe'
a=config(r/'out/.config'); b=config(n/'.config')
diff={k:[a.get(k,'n'),b.get(k,'n')] for k in a.keys()|b.keys() if a.get(k,'n')!=b.get(k,'n')}
assert diff=={'CONFIG_KEXEC':['n','y'],'CONFIG_KEXEC_CORE':['n','y'],'CONFIG_CRASH_CORE':['n','y']},diff
for name in ('CFI_CLANG','CFI_CLANG_SHADOW','SHADOW_CALL_STACK','LTO_CLANG_FULL','MODVERSIONS','META_SAMPLE_PGO'):
    assert b['CONFIG_'+name]=='y',name
release=(n/'include/config/kernel.release').read_text().strip()
assert release=='5.10.246-gd7102a837402-qkx-native-probe'
assert (n/'arch/arm64/boot/Image').read_bytes()[56:60]==b'ARM\x64'
elf=ELF(n/'vmlinux');syms=elf.symbols()
for name in ('machine_kexec','kernel_kexec','__arm64_sys_kexec_load','__cfi_check'):
    assert name in syms and syms[name][0]!=0,name
assert elf.section('.BTF')[:2]==b'\x9f\xeb'
log=(r/'native-kexec-full-build.log').read_text()
assert 'BTFIDS  vmlinux' in log and 'SYSMAP  System.map' in log
assert not re.search(r'FAILED|error:|\*\*\*',log)
exports={line.split()[1]:int(line.split()[0],16) for line in (n/'Module.symvers').read_text().splitlines()}
modules=[]
for line in (n/'modules.order').read_text().splitlines():
    path=Path(line);path=path if path.is_absolute() else n/path
    module=ELF(path);versions=module.section('__versions')
    assert len(versions)%64==0,path
    for pos in range(0,len(versions),64):
        crc=struct.unpack_from('<Q',versions,pos)[0];name=ELF.string(versions,pos+8)
        assert exports.get(name)==crc,(path,name)
    assert any(x.startswith(b'vermagic='+release.encode()+b' ') for x in module.section('.modinfo').split(b'\0')),path
    symbols=module.symbols()
    assert '__cfi_check' in symbols and symbols['__cfi_check'][0]!=0,path
    modules.append({'module':str(path.relative_to(n)),'crc_matches':len(versions)//64,'cfi_check':True})
assert modules
stock=baseline['exports']
changed=[name for name in stock.keys()&exports.keys() if stock[name]!=exports[name]]
subprocess.run([str(r/'sysroot/usr/sbin/bpftool'),'btf','dump','file',str(n/'vmlinux'),'format','raw'],stdout=(n/'btf-check.raw').open('w'),check=True)
assert "FUNC 'vfs_truncate'" in (n/'btf-check.raw').read_text()
report={'release':release,'config_changes':diff,'kexec_linked':True,'cfi_scs_preserved':True,
        'module_count':len(modules),'modules':modules,'stock_export_crc_changes':changed,
        'new_exports':sorted(exports.keys()-stock.keys()),'removed_exports':sorted(stock.keys()-exports.keys()),
        'warnings':[line for line in log.splitlines() if 'warning:' in line],
        'hardware_tested':False,'boot_image_packaged':False,'stock_module_execution_still_blocked':True}
(r/'native-kexec-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
