# Leaf — revisão de limites e vínculo local de callers/imports

**68 grupos host aprovados, zero falhas/ignorados.** Revisão e endurecimento do
verificador estático existente, sem novo grupo de testes, helper ou verificador
genérico de proveniência/build. Nenhum build kernel/Android, alteração do loader,
inserção, transferência ou operação no Quest.

## 1. Limites de quantidade não bastavam para controlar o custo

A revisão encontrou dois custos evitáveis no parser anterior:

- Cada lookup de nome recopiava a tabela de strings inteira e procurava seu
  terminador sem limite individual.
- Cada referência de call procurava o caller percorrendo todos os símbolos.
  Muitos símbolos/referências poderiam produzir trabalho quadrático, apesar dos
  limites globais de quantidade.

`cache_leaf_static_review.py` agora:

1. Procura nomes diretamente nos bytes originais, sem recópia da tabela, com
   cache por tabela/offset, limite individual de **1.024 bytes** e orçamento
   cumulativo de **4 MiB** para nomes únicos, incluindo terminadores.
2. Resolve queries de caller por uma varredura ordenada com heap/conjunto ativo,
   preservando ambiguidade. Não escolhe arbitrariamente um caller sobreposto.
3. Expõe métricas de símbolos, relocações, queries e strings para auditoria.
4. Recusa seções comprimidas, índice de seção de símbolo estendido e declaração
   insuficiente de alinhamento da seção de código, em vez de presumir suporte.

As restrições são do **perfil do parser**, não uma afirmação de que todo ELF
fora delas seja inválido. Permanecem os limites anteriores de arquivo, tabelas,
instruções e estados CFG. Não há promessa de latência rígida ou sandbox contra
todo input host adversarial; a análise continua sem executar bytes inspecionados.

O teste existente ganhou controles dos novos limites/formatos e 10.000 queries
de callers, incluindo ambiguidade, seções diferentes e borda de instrução.
Esse teste demonstra resultados da implementação, não benchmark temporal nem
prova exaustiva de complexidade.

## 2. Auditoria pontual do ELF histórico

Artefato: `quest3/module/quest_kexec.ko`, SHA-256
`0ad15a9d9ae707c228e686f590541a046445fbdcd27289a985776fb326884880`.
Config/symvers usados para confronto: preparação stock existente em
`.work/cma-identity-stock-out/`. O symvers permanece
`c250004c0e4ac84ca2d83797109f08d7adf31b9c76450dd5a4fcc996b0a48078`.

Foram vinculados **por conteúdo local** ELF, fontes atuais, registros `.cmd`,
config e tabela de exports. Não se executaram os comandos históricos e não se
concluiu que esses arquivos bastem para reproduzir/atestar o build.

| Checagem observada | Resultado |
|---|---|
| `__versions` versus indefinidos | 72 registros = 71 indefinidos + module_layout |
| CRCs contra tabela stock fornecida | 72 correspondências, nenhuma divergência |
| Provedores registrados | vmlinux e `drivers/firmware/qcom-scm` |
| Namespace requerido pelos imports | VFS_internal_I_am_really_a_filesystem_and_am_NOT_a_driver |
| Declaração de namespace no ELF | Presente; aplica-se a kernel_read e filp_open |
| Licença/dependência ELF | GPL; `depends=qcom-scm` |
| Calls diretos observados ao leaf | Dois em qkx_test_transition e um em qkx_test_full_copy |
| Parser no artefato | 432 símbolos, 20.943 relocações, 3 queries de call e 6.138 bytes de nomes únicos |

**Nem todos os imports vêm de vmlinux.** Os quatro `qcom_scm_*` observados
dependem do provider `drivers/firmware/qcom-scm`; a config preparada registra
`CONFIG_QCOM_SCM=m` e o ELF declara essa dependência. Não reclassificar esses
imports como built-in só por seus CRCs coincidirem. A resolução/availability e
referências de lifetime de eventual carga real não foram demonstradas. Isso
também não autoriza nova inserção para verificá-las.

É auditoria comparativa do artefato histórico, **não uma allowlist aprovada para
um futuro módulo de staging/helper**. Conferir CRCs não prova semântica completa,
CFI do alvo indireto, segurança da chamada ou equivalência ao binário fabricante.

## 3. Comandos de build: o que se consegue e não se consegue vincular

Os primeiros comandos registrados em `.loader.o.cmd`, `.quest3-scm.o.cmd` e
`.quest3-platform.o.cmd` contêm CFI/cross-DSO, SCS, Full LTO, x18 reservado e
stack protector strong. O comando de assembly `.transition.o.cmd` não recebe
instrumentação C; não tratar isso como prova de que o corpo ASM foi protegido
automaticamente. O comando de metadados `.quest_kexec.mod.o.cmd` conserva
SCS/LTO/x18 e não recebe CFI, conforme a exceção Kbuild já revisada.

O caller fonte declara `extern void qkx_flush_dcache_area(void *, size_t)` com
nomes de argumentos. Isso é uma observação textual, não verificação completa de
tipo após includes/macros/LTO. Os registros apontam para caminhos históricos
`/workspace/quest3-build/...`; guardar seu texto e hashes **não** comprova qual
conteúdo de cada header/fonte transitivo estava nesses caminhos ao compilar.
Os comandos de link contêm múltiplas operações históricas: foram armazenados,
nunca executados nesta revisão.

O vínculo preservado consiste em hashes dos arquivos atuais, nomes de unidades,
protótipo observado, calls/relocações e interfaces do ELF. Faltam relação de build
autenticada/reproduzida, dependências transitivas completas e prova de ABI C dos
callers. Não promover L01/L02/L03/L04/L05/L10 a PASS de contrato por causa desse
ledger de evidência. Não há novo verificador genérico dessas obrigações.

## 4. Estado dos critérios e próximos gates

O verificador mantém resultado global somente PENDING/REJECT. O ELF histórico
continua **REJECT em L08** pelo perfil PAC novo; L06/L07/L09/L13 têm apenas seus
PASS estáticos limitados. Novos limites não aprovaram o artefato nem alteraram
seus bytes. Cache real, lifetime, autorização, helper_approved e boot_ready
continuam não demonstrados/falsos.

Próximo gate offline: tornar reutilizáveis as checagens de conteúdo e interfaces
(`__versions`, CRC/provedor/namespace e política explícita de imports), com
controles negativos de substituição e sem confundir consistência de metadados
com prova de build/CFI/lifetime. Isso não inclui helper, wrapper operacional,
novo build de módulo, adaptação do loader ou execução no aparelho.

Estimativa global permanece ~40% subjetiva. Evidências, fontes e comandos
somente lidos foram preservados em
`private-diagnostics/cache-leaf-parser-caller-review-01/`, junto da suíte e hashes.
