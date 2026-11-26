from pathlib import Path
import difflib,hashlib,json,shutil,tarfile,tempfile,subprocess
r=Path('/workspace/quest3-build');p=r/'local-complete';(p/'module').mkdir(parents=True,exist_ok=True)
base=r/'gpu-pm-fix/module';patch=''
for old in sorted(base.iterdir()):
 n=old.name;new=r/'module'/n;shutil.copy2(new,p/'module'/n)
 if old.suffix in ('.c','.h','.S') or n=='Makefile':
  patch+=''.join(difflib.unified_diff(old.read_text().splitlines(True),new.read_text().splitlines(True),fromfile='a/module/'+n,tofile='b/module/'+n))
(p/'from-gpu-pm.patch').write_text(patch)
with tempfile.TemporaryDirectory() as tmp:
 shutil.copytree(base,Path(tmp)/'module')
 subprocess.run(['git','-C',tmp,'apply','--check',str(p/'from-gpu-pm.patch')],check=True)
for folder in ['tests','device-tools']:
 shutil.copytree(r/folder,p/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
for name in ['CHECKLIST.md','remaining-private-symbols.md','native-kexec-plan.md','local-checks.json','local-checks.log','checklist-build.log','validation.json','run-local-checks.py','verify.py','verify-cfi-guards.py','verify-platform.py','verify-native-kexec.py','q3make','build.sh','env.sh']:
 shutil.copy2(r/name,p/name)
(p/'README.md').write_text('''# Entrega local consolidada

Leia CHECKLIST.md para estados, evidências e ordem de testes no aparelho. Os módulos em module/ são para o kernel stock reproduzido 5.10.246-gd7102a837402. O kernel experimental nativo é um arquivo separado e não pode usar indiscriminadamente os módulos stock.

Esta entrega inclui as correções anteriores e a mudança de ordem SCM: preparar/validar imagens e realizar consultas antes da única alteração persistente permitida. Duas alterações SCM na mesma carga ou alteração combinada com testes/execução são recusadas. O patch incremental aplica sobre o pacote GPU-PM anterior e passou em git apply --check.

Os dez checks locais passaram. O teste x18 modela pilha/registradores usando o desassembly e usa o binário original como controle negativo; não executa instruções privilegiadas. Os testes de drivers/SCM/CPU usam mocks. Nenhum artefato foi carregado no aparelho nesta sessão.

ADB com root foi confirmado pelo usuário em seu computador; método de boot/recuperação não confirmado. device-tools contém coletor verificado e instruções. Use o arquivo compactado para preservar a indentação do Python. Nenhum teste automático deste pacote executa ADB real ou carrega módulos: a suíte do coletor usa ADB simulado.

Os scripts de build/verificação pressupõem /workspace/quest3-build, sua árvore de kernel, toolchain e entradas originais. Esses componentes grandes não estão incluídos; logs e manifestos registram os resultados. O preflight independente continua usando preflight_only=1 execute=0. A execução dependente de símbolos privados continua bloqueada sob CFI.
''')
(p/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(p))+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS'))
with tarfile.open(r/'quest3-local-complete.tar.gz','w:gz') as t:t.add(p,arcname='quest3-local-complete')
# Package the native kernel and all of its verified modules, never stock modules.
n=r/'native-kexec-probe';meta=r/'native-kexec-package';meta.mkdir(exist_ok=True)
v=json.loads((r/'native-kexec-validation.json').read_text())
(meta/'README.md').write_text(f'''# Kernel nativo experimental, não instalado

Release: {v['release']}

Image ARM64 e {v['module_count']} módulos desta mesma compilação. CFI/SCS/Full LTO preservados. As únicas mudanças de configuração são KEXEC/KEXEC_CORE/CRASH_CORE. Há {len(v['stock_export_crc_changes'])} CRCs exportados diferentes do conjunto stock; não misture módulos dos dois conjuntos.

O kernel completo e os módulos passaram por compilação e verificação de BTF/CRC/CFI. Não há boot.img, vendor_boot, DTBO, initramfs do aparelho ou validação da cadeia de boot neste pacote. Não foi instalado, inicializado nem usado para executar kexec no Quest. O suporte nativo oferece uma alternativa de integração, mas não comprova que os drivers da placa realizam todo o desligamento exigido.

Consulte native-kexec-plan.md e CHECKLIST.md. O acesso root confirmado não confirma, por si só, um método seguro/funcional para iniciar ou recuperar este kernel.
''')
items=[(n/'arch/arm64/boot/Image','Image'),(n/'.config','kernel.config'),(n/'Module.symvers','Module.symvers'),(n/'System.map','System.map'),(n/'modules.order','modules.order'),(meta/'README.md','README.md')]
for name in ['native-kexec-validation.json','native-kexec-full-build.log','native-kexec-configure.log','native-kexec-plan.md','CHECKLIST.md']:
 items.append((r/name,name))
for module in v['modules']:
 path=module['module'];items.append((n/path,'modules/'+path))
(meta/'SHA256SUMS').write_text(''.join(hashlib.sha256(src.read_bytes()).hexdigest()+'  '+dest+'\n' for src,dest in items))
items.append((meta/'SHA256SUMS','SHA256SUMS'))
with tarfile.open(r/'quest3-native-kexec-experimental.tar.gz','w:gz',compresslevel=3) as t:
 for src,dest in items:t.add(src,arcname='quest3-native-kexec-experimental/'+dest)
for name in ['quest3-local-complete.tar.gz','quest3-native-kexec-experimental.tar.gz']:
 p=r/name;print(name,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
