# Lifetime e ABI/CFI do eventual helper — revisão de evidências offline

**Revisão concluída, sem helper novo ou admissão runtime.** Permanecem 67 grupos
host, zero falhas/ignorados; nenhum grupo novo foi adicionado. Não houve build
kernel/Android, alocação, mapping, escrita de payload, transferência ou operação
no Quest. Loader/assembly e referências host anteriores permanecem inalterados.

Esta revisão continua o [vínculo host](2026-11-18-staging-binding-host.md) e
identifica o que seria necessário para substituir suas claims por garantias
reais. Ela **não substitui** essas claims por observações do alvo.

## 1. Três lifetimes que não podem ser confundidos

| Objeto | Evidência local disponível | Garantia que ainda falta |
|---|---|---|
| Descritor/pool default | `reserved_mem[]` e `cma_areas[]` têm armazenamento estático no fonte; inicialização de boot e config sem OF_DYNAMIC/OVERLAY | Identidade no boot aplicável, ativação/capacidade e aplicabilidade do racional de lifetime ao binário/plataforma reais |
| Páginas adquiridas | Contratos de retorno CMA/buddy e pares de release, revistos offline | Aquisição efetiva autorizada, retenção contínua dos objetos originais, nenhum free/reuso e nenhum acesso pendente |
| Mappings/código/tabelas | Traduções e layouts de referência; artefatos antigos para inspeção ABI | VA/PA/atributos reais válidos durante todas as fases, código/tabelas finais publicados e entrada arquitetural revisada |

`drivers/of/of_reserved_mem.c:25-27,425-440` mantém array estático e retorna um
ponteiro para a entrada encontrada pelo nome do nó. Embora o comentário use
"reference", o corpo **não incrementa refcount nem adquire trava de lifetime**.
`mm/cma.c:48-66,106-150` mantém array de áreas e ativa/verifica a área no boot;
falha pode zerar count. `cma_get_name` apenas retorna nome.

O racional de armazenamento estático/config de boot é mais específico que uma
amostra de PFNs, mas não demonstra aquisição das páginas ou segurança DMA.
`READ_ONCE` e comparação repetida em `q3_cma_identity.c:88-105` continuam checks
de consistência, não pinagem ou proteção ABA. A consulta de identidade permanece
não executada e seu controlador, desarmado.

Um contrato operacional teria de manter area/page/count originais para CMA e
VA/size originais para buddy exact, incluindo dono responsável e estado de uso
único até o último acesso. Não reconstruir posse a partir de hash/ID/endereço;
não usar `get_page` sobre RAM arbitrária como substituto de aquisição CMA/buddy.
Lifetime do módulo, lifetime das páginas e exclusão de writers/DMA são obrigações
distintas. Uma referência de módulo também não impede unbind de driver; isso já
é explicitado em `quest3-platform.c:18-29`.

## 2. Não usar hotplug lock como lease genérico até o salto

`mm/memory_hotplug.c:55-95` implementa:

- `get_online_mems`/`put_online_mems`: read lock de `mem_hotplug_lock`.
- `mem_hotplug_begin`: `cpus_read_lock()` seguido do write lock de memória.

Os dois accessors de memória **não constam na tabela stock de exports fornecida**.
Não resolver endereços privados nem assumir que sua existência interna ofereça
um handle publicamente utilizável por módulo.

Além disso, há um ciclo potencial de lock order a evitar em qualquer redesign:

1. Caller mantém read lock de memória para tentar garantir lifetime.
2. Offliner concorrente mantém `cpus_read_lock` e espera o write lock de memória.
3. Caller tenta shutdown de CPUs, cujo caminho `_cpu_down` exige
   `cpus_write_lock` (`kernel/cpu.c:1058-1071,1121-1126,1406-1445`).

Esse interleaving forma espera circular. É análise de possibilidade no fonte,
**não deadlock observado ou modelo exaustivo da plataforma**. Não segurar essa
trava através do shutdown por conveniência, nem soltá-la e alegar que a garantia
continua automaticamente. Uma solução precisaria de argumento de lifetime e
lock ordering próprio, sem bloquear CPUs necessárias à sua conclusão.

O offline normal usa `MIGRATE_MOVABLE` (`memory_hotplug.c:1545-1549`), e
`has_unmovable_pages`, `mm/page_alloc.c:8618-8627`, recusa pageblock CMA quando
o migratetype pedido não é CMA. `page_isolation.c:24-64` também rejeita isolamento
concorrente e propaga EBUSY. Isso sustenta parte do racional anterior de CMA
nos caminhos normais, não imunidade a clientes externos/hipervisor, ausência de
DMA ou equivalência completa do binário stock. Não alterar migratetype/hotplug
para contornar falhas nem apropriar-se de pools dedicados.

## 3. Chamada direta não é alvo indireto CFI

Foram inspecionados arquivos **já existentes**, sem compilar ou executá-los:

- `quest3/module/quest_kexec.ko`, artefato histórico corrigido, SHA-256
  `0ad15a9d9ae707c228e686f590541a046445fbdcd27289a985776fb326884880`.
- Disassembly/relocações com LLVM local Android r450784e e símbolos via llvm-nm.
- Fontes locais do kernel, HEAD `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`.

O ELF tem **três relocações `R_AARCH64_CALL26`** para
`qkx_flush_dcache_area`, associadas a instruções `bl`. São calls diretos de
caminhos históricos de testes; não são prova de execução histórica ou futura.
O corpo inspecionado tem `hint #34` (BTI c), operação `dc civac`, `dsb sy` e
`ret`. Usa x0–x3 e flags; não altera x18, x19–x29, SP ou LR no corpo leaf.
Não contém chamada aninhada ou troca de MMU nesse helper.

O módulo também define `__cfi_check` e importa o handler CFI abort. Isso demonstra
propriedades desse **artefato**, não que qualquer endereço ASM pertença a um
type-id aceito para chamada indireta. Não foi demonstrada tal associação para
um novo helper. Não transformar casts, símbolos de kprobe ou endereço de bytes
copiados em callbacks por ter um protótipo C semelhante.

`include/linux/cfi.h` distingue suporte a jump tables, e
`arch/arm64/include/asm/memory.h:311-345` explica que endereço de função CFI pode
ser entrada de jump table, não começo do corpo. Isso é um alerta de revisão,
não autorização para usar `function_nocfi`, resolver símbolos privados ou
contornar CFI. O guard em `loader.c:207-215` permanece intacto e bloqueia o
caminho privado sob CFI.

**Direção limitada para estudo:** caso se proponha um helper leaf local no
futuro, preferir um contrato explícito de chamada direta conhecida, sem callback
ou endereço que escape. Validar o ELF final para verificar que o toolchain/LTO
realmente preservou esse contrato. Isso não aprova implementar o helper agora
e não valida a entrada sem retorno de um kernel novo.

## 4. BTI, SCS e ABI: obrigações separadas

`asm/linkage.h:7-43` acrescenta BTI às entradas `SYM_FUNC_START` quando configurado.
`include/linux/linkage.h:221-275` fornece a anotação ELF de função. Essas macros
não demonstram sozinhas membership CFI de um alvo indireto ou segurança de um
trampoline. `SYM_CODE_START` é destinado a código especial, não uma função C
com contrato de retorno ordinário.

`asm/scs.h:9-19` reserva x18 como shadow stack pointer. O Kbuild usa
`-fsanitize=shadow-call-stack` e `-ffixed-x18` para C; CFI cross-DSO e Full LTO
também estão configurados. Esses flags **não instrumentam automaticamente todo
corpo assembly manuscrito**. Um leaf com retorno não deve clobber x18 nem os
callee-saved; adicionar calls, frame ou uso de LR muda as obrigações.

Para qualquer novo artefato, antes de alegar conformidade seriam necessários:

- Declaração exata de parâmetros/retorno, unidades e larguras sob ABI ARM64 LP64;
  sem diferenças ocultas entre C e assembly, callbacks e corpo real.
- Disassembly final e relocações: calls diretos pretendidos, BTI quando exigido,
  nenhuma resolução privada, preservação de x18/callee-saved/SP/LR e frames
  alinhados. Revisão de PAC/return protection conforme configuração, sem inferir
  isso apenas de flags da unidade C ou de landing pad BTI.
- Retenção de CFI estrito, SCS, Full LTO, MODVERSIONS e proteções existentes;
  CRCs/namespaces dos imports aplicáveis. Símbolo local não tem CRC de import;
  isso não elimina a validação da ABI interna ou de seus callers.
- Revisão de code lifetime, alternatives/errata, atributos de mapping, ranges,
  zero length/overflow/linhas e contexto de CPU/IRQs/preempção.
- Protocolo PoC, publicação de código/I-cache e ausência de writes/DMA posteriores,
  separados do fato de que uma função chama/retorna segundo a ABI.

O teste existente `x18-frame-test.py` modela saves/restores da roundtrip em
disassembly. Ele não emula caches/MMU/EL1 e não valida esse futuro helper ou
entrada sem cópia. A inspeção leaf desta revisão também não faz isso.

## 5. Matriz para substituir claims — ainda sem substituição real

| Claim host | Evidência/garantia necessária | Estado atual |
|---|---|---|
| `real-handles-retained-including-transition` | Retornos reais autorizados, objetos originais retidos, estado de release único, nenhuma perda de handle/acesso pendente | Ausente; fixtures não são handles |
| `default-cma-identity-and-lifetime` | Identidade no boot aplicável e racional revisado de lifetime/plataforma, sem lease inventado por accessor | Racional de fonte parcial; runtime ausente |
| `writable-mappings-and-attributes` | Mappings efetivos de todos os recursos, atributos/aliases/PFNs válidos durante seu uso | Ausente |
| `writer-dma-exclusion` | Exclusividade contínua, I/O concluído e quiescência de clientes/engines relevantes | Ausente; posse por alocador não basta |
| `destinations-clean-to-poc-after-last-write` | Helper aprovado, cobertura real e operação/barreiras adequadas após última escrita | Apenas modelo de intervalos; helper novo ausente |
| `transition-data-code-icache-published` | Bytes e tabelas finais, publicação e lifetime da entrada revisados | Geometria/claims apenas |
| `cfi-scs-entry-reviewed` | Call graph/ELF e contrato arquitetural específico da entrada, sem bypass | Inspeção de artefato antigo não satisfaz |

## Resultado e próximo gate

**Não há evidência suficiente para promover claims a autorização ou readiness.**
É possível distinguir uma chamada direta leaf existente de um novo alvo indireto,
mas não concluir por isso que cache, lifetime ou handoff estão prontos. Nenhum
gate runtime foi liberado, e nenhum helper foi implementado.

Próximo passo seguro: definir critérios verificáveis de aceitação/rejeição do
contrato de um eventual helper leaf direto, incluindo ABI/CFI/SCS/BTI/PAC e
limites de ranges, antes de qualquer implementação. O lifetime real continua
gate independente. Qualquer experimento no Quest exige autorização nova e
específica; recibos, âncoras e autorizações consumidas não a substituem.

Evidências em `private-diagnostics/lifetime-helper-abi-review-01/`: snapshots de
fontes/config/exports, disassembly/símbolos do ELF antigo, matriz, suíte e hashes.
Arquivos anteriores, candidatos e controlador desarmado preservados.
