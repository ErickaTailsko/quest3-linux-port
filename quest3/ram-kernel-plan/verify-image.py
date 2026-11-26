#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,subprocess
r=Path(__file__).resolve().parents[1];out=r/'ram-first-kernel'
subprocess.run(['python3',str(r/'ram-kernel-plan/verify-config.py')],check=True)
image=out/'arch/arm64/boot/Image';vmlinux=out/'vmlinux'
assert image.read_bytes()[56:60]==b'ARM\x64'
assert (out/'include/config/kernel.release').read_text().strip()=='5.10.246-gd7102a837402-q3-ram-first'
mapping=json.loads((r/'ram-kernel-plan/module-config-map.json').read_text())
builtins={x.removeprefix('kernel/') for x in (out/'modules.builtin').read_text().splitlines()}
missing=[x['file'] for x in mapping.values() if x['file'] not in builtins]
assert not missing,missing
llvm=r/'clang-prebuilts/clang-r450784e/bin'
undef=subprocess.check_output([str(llvm/'llvm-nm'),'-u',str(vmlinux)],text=True)
strong=[l for l in undef.splitlines() if l.split()[0]=='U']
assert not strong,strong
weak=[l.split()[-1] for l in undef.splitlines() if l.split()[0] in ('w','v')]
assert set(weak)<={'efi_attr_config_table','efi_attr_fw_vendor','efi_attr_runtime'},weak
# Avoid loading the huge complete symbol table into memory.
p=subprocess.Popen([str(llvm/'llvm-nm'),str(vmlinux)],stdout=subprocess.PIPE,text=True)
cfi=False
for l in p.stdout:
 if l.rstrip().endswith(' __cfi_check'):cfi=True
assert p.wait()==0 and cfi
for file in ['drivers/usb/dwc3/.dwc3-msm-core.o.cmd','drivers/usb/phy/.phy-msm-snps-hs.o.cmd','drivers/usb/phy/.phy-msm-ssusb-qmp.o.cmd']:
 s=(out/file).read_text();assert '-fsanitize=cfi' in s and '-fsanitize=shadow-call-stack' in s,file
status=subprocess.check_output(['git','status','--porcelain'],cwd=r/'kernel',text=True)
assert not status.strip()
log=(out/'build.log').read_text();assert 'error:' not in log and 'Error ' not in log
warnings=[x for x in log.splitlines() if 'warning:' in x]
result={'image_bytes':image.stat().st_size,'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
 'release':(out/'include/config/kernel.release').read_text().strip(),'all_selected_provider_modules_builtin':True,
 'provider_count':len(mapping),'cfi_scs_in_USB_compile_commands':True,'unresolved_strong_symbols':strong,'optional_weak_EFI_symbols':weak,
 'kernel_source_clean':True,'warnings':warnings,'boot_tested':False,'USB_enumeration_tested':False,
 'ADSP_transport_adoption_validated':False,'retained_log_validated':False}
result['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r/'kernel',text=True).strip()
result['initramfs_sha256']=hashlib.sha256((r/'ram-first/quest3-ram-first.cpio.gz').read_bytes()).hexdigest()
result['boot_ready']=False
(r/'ram-kernel-plan/image-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
