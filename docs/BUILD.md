# Reproduzir e verificar

## O que foi usado

- Fonte kernel pública: facebookincubator/oculus-linux-kernel,
  `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`.
- Toolchain Android Clang/LLD14.0.7, `clang-r450784e`, commit de prebuilts
  `425c8149f17c8d9914bf690b4d5abe45a13fb993`.
- Kernel stock identificado como5.10.246-gd7102a837402; o commit interno
  gd7102a837402 não foi identificado na fonte pública.
- pahole1.32 adaptado: fonte completa em `quest3/inputs/dwarves-quest3-cfi`.
- BusyBox1.36.1; GCC cross Debian14.2.0-19cross1, glibc2.41-11cross1,
  QEMU aarch6410.0.13 na construção registrada.

As árvores completas de compilação e toolchains não estão no Git. As receitas
originais do ambiente foram preservadas em `quest3/`; seus caminhos absolutos
são históricos. Para um clone novo, prefira os helpers abaixo.

## Testes host sem Quest

Requisitos: Python3, compilador C nativo, make/bash; testes opcionais de
desassembly precisam LLVM. Execute na raiz:

```sh
python3 tools/verify-manifest.py
python3 tools/run-host-checks.py
```

`--report caminho.json` salva o resultado em outro caminho. A suíte não chama
ADB real, não carrega módulos e não solicita reset. Testes que exercitam
controladores ADB substituem seu subprocesso por mocks. Presença de hardware
conectado não é necessária.

Para incluir a verificação de binários CFI e do frame x18 com LLVM14:

```sh
export Q3_LLVM=/caminho/clang-r450784e/bin
export Q3_OBJDUMP="$Q3_LLVM/llvm-objdump"
python3 tools/run-host-checks.py
```

Os testes reais de MMU/CPU, boot, USB e firmware não são substituídos por esses
modelos. `manifests/host-tests.json` registra a execução desta publicação.

## Preparar fontes e pahole

Em Debian/Ubuntu, os builds requerem git, cmake, make, ninja/gcc/g++, flex,
bison, bc, pkg-config, libssl-dev, libelf-dev, libdw-dev, zlib1g-dev,
liblzma-dev e libzstd-dev. O embedded libbpf está na fonte pahole vendorizada.
Use o gerenciador de pacotes da sua distribuição; não altere credenciais ou
configurações de rede para reproduzir o ambiente.

```sh
bash tools/setup-sources.sh
cmake -S quest3/inputs/dwarves-quest3-cfi -B .work/pahole-build \
  -DCMAKE_BUILD_TYPE=Release -DLIBBPF_EMBEDDED=ON
cmake --build .work/pahole-build --target pahole -j4
```

O setup baixa revisões fixadas para `.work/`; não executa testes no aparelho.
Se uma árvore já existir com outra revisão, ele para para preservar o trabalho.

## Kernel stock e módulos

```sh
mkdir -p .work/out
cp quest3/configs/stock-device.config .work/out/.config
tools/q3make olddefconfig
```

Confira que CFI_CLANG, CFI_CLANG_SHADOW, SHADOW_CALL_STACK, LTO_CLANG_FULL e
MODVERSIONS continuam habilitados. O PGO do fabricante usa vmlinux.profdata;
o arquivo correspondente deve estar presente na fonte, conforme os relatórios.
Não desligue proteções para contornar falhas.

```sh
tools/q3make -j4 Image modules
tools/q3make -j4 M="$PWD/quest3/module" modules
```

Module.symvers precisa vir do build completo correto. `modules_prepare`
isoladamente não substitui a produção dos CRCs com MODVERSIONS/Full LTO.
O build LTO registrado usou cerca de25GiB de memória em seu pico e levou vários
minutos; considere swap e espaço para fontes e múltiplas saídas de vários GiB.

Os headers públicos usados pelo módulo são da mesma árvore do kernel,
incluindo DWC3/Gunyah. O header SCM legado de compatibilidade é histórico;
o caminho atual usa as interfaces oficiais exportadas.

## Kernel alvo RAM-first

Para a preparação de um candidato QMP separado, consulte
[estado e receita](reports/2026-11-16-qmp-build-preparation.md).
`tools/build-qmp-candidate.sh` não substitui o Image publicado; disponibilidade
dos drivers e handshake herdado são validações distintas.
Após um build completo, executar `tools/verify-qmp-candidate.py --out CAMINHO`
antes de considerar os artefatos consistentes. Essa checagem não libera boot.
A receita atual executa esse verificador automaticamente ao final. O primeiro
build desta sessão foi retomado manualmente e recebeu a mesma verificação
após concluir; [resultado](reports/2026-11-16-qmp-build-result.md).

```sh
mkdir -p .work/ram-first-out
cp quest3/configs/ram-first.config .work/ram-first-out/.config
Q3_OUT="$PWD/.work/ram-first-out" \
Q3_LOCALVERSION=-gd7102a837402-q3-ram-first tools/q3make olddefconfig
Q3_OUT="$PWD/.work/ram-first-out" \
Q3_LOCALVERSION=-gd7102a837402-q3-ram-first tools/q3make -j4 Image modules
```

O Image publicado é o candidato identificado em docs/STATUS.md. O target
continua sem KEXEC nativo habilitado; a alternativa nativa experimental está
arquivada separadamente e não equivale a esse candidato.

## BusyBox, initramfs e DT

`quest3/ram-first/rebuild-busybox.sh` requer um cross GCC ARM64 com libc
estática e recebe diretório de saída novo. A fonte tar, configuração e
licenças estão incluídas. O script permite CROSS_COMPILE/BUSYBOX_SYSROOT.
`build.py` produz o CPIO e rejeita ELF dinâmico/arquitetura errada; o verificador
independente usa QEMU ARM64 quando configurado. Leia os argumentos de cada
script antes de gerar um arquivo novo.

Para o USB mínimo, use os arquivos de `quest3/usb-minimal`, não o initramfs
anterior de referência. O gerador DT aceita uma captura real e cria uma cópia,
preservando as demais propriedades; não aplique um DTS de Quest2/Pro sem revisão.
`layout-review/check-layout.py` confere Image/initramfs/DT/iomem e só ajusta
os dois endereços de initramfs se `--out-dtb` for explicitado.

As propriedades dinâmicas de uma captura DT antiga não devem ser confundidas
com o estado de um boot novo. As cópias brutas publicadas são evidência histórica,
não um DT de instalação universal. Nenhum desses builds libera o salto CFI.
