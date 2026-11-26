# Identidade CMA padrão — módulo ARM64 construído e verificado no host

> Revisão posterior: [transporte e recuperação](2026-11-17-cma-transport-recovery-review.md).
> Cleanup após timeout agora é bloqueado: o comando remoto pode continuar ativo.
> O módulo deste build não mudou; controlador e testes evoluíram para 46 checks.

**Build stock separado concluído, verificação de artefato aprovada.** Nenhuma
transferência, carga de módulo, consulta runtime, alocação de payload ou operação
ADB foi realizada. O controlador continua com `EXPECTED_MODULE = None`, sem
transporte real. Este resultado não é autorização de implantação.

## Artefato e origem

| Item | Resultado |
|---|---|
| Módulo | q3_cma_identity.ko |
| Tamanho | 280.784 bytes |
| ELF | ELF64 little-endian, AArch64, relocatable |
| Vermagic | `5.10.246-gd7102a837402 SMP preempt mod_unload modversions aarch64` |
| Make | retorno zero, sem warning/error/fatal no log deste build |
| Entradas de versão | 23, incluindo module_layout |
| Símbolos indefinidos | 22, exatamente as versões menos module_layout |

Módulo SHA-256:
`21f62fad44c8ba33c3a16024d87f5c38406cfc20dd374643952b93578cfbd15e`.
Fonte SHA-256:
`fe36f4a50027211b80026e37a46610c422475139ac4efe0c464431941ccebb37`.

Fonte kernel: `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`, com somente a alteração
host já revisada em scripts/extract-cert.c. Clang Android r450784e/14.0.7.
Foi copiada a preparação stock existente para `.work/cma-identity-stock-out/`;
o módulo foi construído em `.work/cma-identity-module-src/`, sem objetos de
módulo anteriores nessa nova pasta. Não foi feito build frio de todo o kernel,
novo Image, módulos completos ou prova de reprodutibilidade binária.

```sh
Q3_OUT="$PWD/.work/cma-identity-stock-out" tools/q3make -j2 \
  HOSTCFLAGS=-DOPENSSL_NO_ENGINE M="$PWD/.work/cma-identity-module-src" modules
```

Fonte/Makefile foram copiados do protótipo público; config e symvers vieram da
preparação stock, não de QMP/trim3. Hashes da preparação original reconferidos:

- Config preparada: `e45b01529aa554bab274e7362b1a052517016314270cdd30adfa20413ea0faed`.
- Config stock capturada: `fa0342f1b1dc12d2a723ecb1e390877b31f729480ad8328a89c1b5ae6b1f9a99`.
- Symvers fornecido: `c250004c0e4ac84ca2d83797109f08d7adf31b9c76450dd5a4fcc996b0a48078`.

A config preparada é a já normalizada nessa árvore, não uma alegação de
igualdade textual com a config runtime. Os candidatos anteriores não foram
substituídos.

## Verificações do próprio .ko

Novo helper: `tools/verify-cma-identity-module.py`, somente arquivos locais e
stdlib Python. Não chama ferramentas de dispositivo nem altera o controlador.

- Exige ELF64 little-endian AArch64 REL e tabelas dentro dos limites do arquivo.
- Confere vermagic, nome, licença GPL, ausência de dependências externas e tipos
  dos parâmetros inspect/attempt.
- Lê os registros ARM64 de 64 bytes em **__versions do binário**; exige conjunto
  exato de 23 imports e CRC/provedor vmlinux iguais à tabela stock fornecida.
  Exige também correspondência com o .mod.c gerado.
- Lê .symtab e exige indefinidos iguais às versões, exceto module_layout,
  além dos símbolos CFI, init/exit, relatório e parâmetros.
- A allowlist não admite cma_alloc/cma_release, buddy, ACR, resolução privada
  de símbolos ou pausa de CPUs. O escopo permanece consulta de identidade.
- Confere hashes de configs/symvers, release preparado e igualdade da cópia
  de fonte usada no build com o fonte público atual.

Imports centrais: dma_contiguous_default_area (`0x4fd950ed`), cma_get_name
(`0x0b8eca36`) e of_reserved_mem_lookup (`0xfece5d03`). Lista completa em
`quest3/cma-identity-query/build-verification.json`. CRCs corretos são evidência
de compatibilidade de versões dos imports, **não prova completa de equivalência
do binário stock ou segurança de lifetime**.

## Proteções e layout

Config/comando da unidade principal mantêm CFI estrito/cross-DSO, SCS, Full LTO
(`-flto`, sem ThinLTO), x18 reservado e stack protector strong; MODVERSIONS
permanece habilitado. O ELF define __cfi_check e importa o handler CFI abort.
O disassembly arquivado mostra save/restore de x30 via x18, consistente com
SCS; não é validação de todos os caminhos runtime.

A unidade de metadados .mod.c tem SCS/LTO/stack protector, mas não recebe CFI:
`scripts/Makefile.modfinal:27` remove CC_FLAGS_CFI nesse passo do Kbuild.
O verificador trata essa exceção separadamente, sem relaxar CFI na consulta.

Guardas e static_asserts compilaram contra os headers preparados: reserved_mem
de 56 bytes; offsets ops=24, base=32, size=40, priv=48. Isso confere o layout
público dessa árvore, não um layout extraído diretamente do binário stock.
Não há leitura de campos privados de struct cma.

## Testes e preservação

`tools/test-cma-identity-module.py` cobre ELF sintético truncado/arquitetura
errada, versões/imports inesperados, CRC/provedor divergente, CFI ausente,
flags conflitantes, procedência e inconsistência do .mod.c. ELF sintético não
é módulo executável nem evidência runtime.

Suíte completa: **45 aprovações, zero falhas e zero testes ignorados**.
O controlador desarmado também continua sendo testado; o build não adicionou
hash aprovado nem adaptador live.

Intenção, resultado e log em `private-diagnostics/cma-identity-build-01/`.
Subpasta artifacts preserva 17 arquivos, incluindo módulo, fonte, configs,
symvers, comandos primário/metadados/LTO/link, .mod.c, relatório, suíte, ELF,
símbolos e disassembly; cópias conferidas por hash em artifact-manifest.json.
Resumo público: `quest3/cma-identity-query/build-verification.json`.

## Gates restantes

Identidade runtime, disponibilidade, posse, segurança DMA e boot continuam
não demonstrados. O accessor não adquire referência de lifetime e reobservar
ponteiros não é trava contra ABA/hotplug. O trim3 continua solicitando todos
os 32 MiB nominais após arredondamento, apesar de image_size de 31,25 MiB;
nenhum sucesso deste build libera aquisição do pool.

Próximo marco: revisar código/transporte e limites de reconciliação, sem
habilitar implantação automaticamente. Eventual transporte real exige revisão
própria e nova autorização específica para uma consulta com cleanup, sem
teste de alocação, payload, desligamento de CPUs ou handoff.
