# Staging direto — confronto offline com fontes/ABI stock

**Revisão de fontes/exports, não implementação.** Suíte existente: 65 grupos,
sem novo grupo de testes nesta revisão. Nenhum build kernel/Android, alocador,
mapping, writer, adaptador, mudança de loader ou operação no Quest.

## Proveniência e alcance

Árvore local `.work/kernel`, HEAD
`dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`. O diff de arquivos rastreados mostra
somente `scripts/extract-cert.c`, alteração host anterior; os arquivos revisados
aqui não foram alterados. Hashes dos fontes da revisão anterior de aquisição
foram reconferidos contra `stock-allocation-source-review.json`.

Config e exports: `.work/cma-identity-stock-out/.config` e `Module.symvers`,
preparação stock anterior. Config preparada SHA-256
`e45b01529aa554bab274e7362b1a052517016314270cdd30adfa20413ea0faed`;
symvers `c250004c0e4ac84ca2d83797109f08d7adf31b9c76450dd5a4fcc996b0a48078`.
É uma config normalizada, não igualdade textual com a config capturada runtime.
NDK userspace não participa desta análise de ABI kernel.

Presença/CRC de export é evidência local de interface fornecida, não prova de
equivalência integral do binário stock, CFI de um futuro módulo, lifetime ou
autorização. Ausência abaixo significa ausência nessa tabela, não impossibilidade
arquitetural nem licença para resolver símbolo privado.

## 1. Interfaces encontradas

| Símbolo | Export stock / CRC | Consequência para o contrato |
|---|---|---|
| `dma_contiguous_default_area` | GPL / `0x4fd950ed` | Ponteiro default acessível; identidade e lifetime runtime continuam pendentes |
| `cma_get_name` | GPL / `0x0b8eca36` | Accessor de nome, não pinagem |
| `cma_alloc` | GPL / `0x8b349932` | Retorna `struct page *`; quarto argumento é `gfp_t` |
| `cma_release` | GPL / `0x43abe439` | Retorno bool, não validador de posse ou proteção contra double-free |
| `alloc_pages_exact` | regular / `0x5fc72f0e` | Retorna VA de área contígua; limitado por MAX_ORDER |
| `free_pages_exact` | regular / `0xeb44339a` | Recebe VA e tamanho originais; não retorna status |
| `kernel_read` | regular / `0x7ddd5d9a`, namespace VFS | Leitor síncrono de buffer kernel; não congela o arquivo |
| `__flush_icache_range` | regular / `0xe2e0c7c6` | Coerência I/D para código, não substituto genérico de clean de payload até PoC |
| `flush_dcache_page` | regular / `0xc7927bec` | Nesta árvore só limpa flag `PG_dcache_clean`, sem operação hardware imediata |
| `vmap` / `vunmap` | regulares / `0x0f3b10bd` / `0x94961283` | Disponibilidade não valida atributos/aliases nem torna necessário criar outro mapping |
| `dma_alloc_from_contiguous`, `dma_release_from_contiguous` | ausentes | Não usar wrappers por endereço privado |
| `cma_get_base`, `cma_get_size` | ausentes | Não usar campos privados/accessors resolvidos indiretamente |
| `__flush_dcache_area`, `__clean_dcache_area_poc`, `__clean_dcache_area_pop` | ausentes | Não há import público desses helpers nesta tabela |
| `__dma_map_area`, `__dma_flush_area`, `sync_icache_aliases`, `arch_wb_cache_pmem` | ausentes | Não são fallback aprovado para a lacuna de cache |

Linhas completas, namespace, tipo e provedor foram preservados em
`private-diagnostics/direct-staging-stock-abi-review-01/symbol-matrix.json`.
Não foi produzido novo ELF/import table ou teste de link dessas APIs.

## 2. Aquisição, alinhamento e liberação

`include/linux/cma.h:56-58` declara:

```c
struct page *cma_alloc(struct cma *cma, size_t count,
                      unsigned int align, gfp_t gfp_mask);
bool cma_release(struct cma *cma, const struct page *pages,
                 unsigned int count);
```

`count` é número de páginas; `align` é ordem em páginas, não bytes.
Para o pedido hipotético de 32 MiB/4 KiB: 8.192 páginas; alinhamento de 2 MiB
corresponde à ordem 9. `mm/cma.c:68-85,437-589` coordena alinhamento/bitmap,
marca intervalo antes da migração e chama o ACR vendor de cinco argumentos.
Há locks, migração/reclaim e retries internos; uma chamada externa não garante
latência rígida nem efeito somente leitura. Não invocar ACR diretamente para
contornar o bitmap, nem converter timeout em autorização de nova tentativa.

Detalhe de portabilidade: wrappers em `kernel/dma/contiguous.c:258-265` usam
`bool no_warn` e limitam alinhamento a `CONFIG_CMA_ALIGNMENT` (8 nesta config,
1 MiB em páginas de 4 KiB). Não transplantar esse protótipo para `cma_alloc`,
nem supor que esse wrapper garantiria os 2 MiB pedidos. O caminho direto de
`cma_alloc` calcula máscara/offset da ordem fornecida; toda base retornada ainda
precisaria passar pelo validador de layout e revisão de posse/lifetime.

`cma_release`, `mm/cma.c:601-623`, confere ponteiros não nulos e PFN inicial no
pool, verifica o fim com `VM_BUG_ON`, libera range e limpa bitmap. Não autentica
o chamador, a tentativa nem se o range já foi liberado. Um `true` não prova
posse anterior ou ausência de DMA. É obrigatório reter area/page/count originais
e estado de uso único; erro inesperado não permite tentar free por outro provider.

Buddy: `mm/page_alloc.c:5436-5523` usa `get_order(size)`, aloca bloco, faz split
e devolve páginas excedentes. `free_pages_exact` recebe **o mesmo VA e size**,
percorre páginas e retorna void. Não inventar um recibo bool de quiescência/free.
Dois slots de 2 MiB são ordem 9, dentro do limite MAX_ORDER=11 já revisado,
mas isso não prova disponibilidade nem posição compatível com a janela initrd.
`__get_free_pages`, linhas 5263-5271, remove `__GFP_HIGHMEM` e retorna
`page_address`; não usar o par `__free_pages` por ordem sobre a área exact split.

Não há promessa estabelecida nesta revisão de que a aquisição CMA inicialize
todos os bytes do staging com zeros. Mesmo que uma política de alocação zere
memória, BSS/tails e readback precisam do contrato explícito. Não tratar o
argumento GFP de CMA como prova automática do zero-fill final dos payloads.

## 3. Mapping e lifetime: o que as conversões não fazem

`include/linux/mm.h:1635-1665` encaminha `page_address` para `page_to_virt` na
config sem HIGHMEM. `arch/arm64/include/asm/memory.h:274-307,347-378` implementa
conversões do linear map e `virt_addr_valid`. São traduções/checks de endereço,
não aquisição, pinagem, autorização ou inspeção de PTE writable. PA de descriptor
histórico ou uma fixture não se torna memória própria por `phys_to_virt`.

`virt_to_phys` não é conversão genérica de VA de `vmap`; esses tipos de mapping
não podem ser misturados. O próprio header também distingue PA de endereço DMA.
Um mapping adicional não é solução automática de atributos/isolamento. Não
criar alias uncached para tentar "provar" readback físico.

`arch/arm64/include/asm/pgtable-prot.h:55-71` define PAGE_KERNEL Normal writable
e não executável, além de variantes. Isso descreve flags de construção, não
comprova os PTEs vivos dos destinos ou a ausência de aliases incompatíveis.
Config preparada: páginas 4 KiB, VA39, SPARSEMEM_VMEMMAP, PAN e zonas DMA/DMA32;
DEBUG_VIRTUAL/KASAN desativados. Nada disso substitui revisão do mapping efetivo.

O racional anterior de lifetime nos caminhos normais de CMA/hotplug continua
limitado ao fonte. Reobservar ponteiros via READ_ONCE no módulo de identidade
não adquire pin de lifetime e não elimina ABA. A consulta não foi executada;
nenhum novo objeto real foi retido nesta revisão.

## 4. Cache: primitiva existente não significa API importável

`arch/arm64/mm/cache.S:99-111` implementa `__flush_dcache_area` com
`dcache_by_line_op civac, sy`: clean + invalidate até PoC.
Linhas 171-192 implementam `__clean_dcache_area_poc` com `cvac, sy`.
O macro em `arch/arm64/include/asm/assembler.h:395-430` alinha início, percorre
linhas e aplica alternativas/errata para determinadas operações. Essa existência
no fonte **não cria export para um módulo**.

Em contraste, `arch/arm64/mm/flush.c:65-80` exporta `flush_dcache_page`, mas o
corpo apenas altera `PG_dcache_clean`, adiando trabalho ao contexto apropriado
de mappings. Não usá-lo para satisfazer o claim `destinations-clean-to-poc`.

`__flush_icache_range`, `cache.S:17-70`, faz coerência de código com alternativas
IDC/DIC e operações até PoU conforme o caminho. `flush_icache_range` inline,
`asm/cacheflush.h:74-96`, ainda chama `kick_all_cpus_sync` salvo exceção KGDB.
Não substituir um pelo outro sem revisar fase/CPUs/IRQs; nem inferir que um
flush de I-cache garante publicação de todos os destinos até PoC.

O loader atual tem helper local `qkx_flush_dcache_area` em
`quest3/module/transition.S:189-203`, com `dc civac`/`dsb sy`. Seu uso final em
`loader.c:837-841` cobre `owned[]` e passa descritores/DT fixos. Não cobre por
contrato os novos handles de destino e não valida um caminho direto. Também não
é prova de equivalência com todas as alternativas/errata do helper stock.
Não foi copiado, estendido ou aprovado para a hipótese direta.

**Lacuna aberta:** selecionar e revisar um mecanismo de manutenção suportado
para o módulo, seus atributos/aliases, errata e contexto de chamada. Ausência de
exports não justifica kprobe/kallsyms privado, desativar CFI ou copiar assembly
sem revisão. Manutenção é só uma obrigação: não impede writers/DMA posteriores.

## 5. I/O e fronteira irreversível

`fs/read_write.c:430-474` expõe `kernel_read` com buffer kernel/offset, valida
área, cria kiocb síncrono e retorna o resultado de read_iter. O caller ainda
trata reads curtas, EOF/erro, progresso e conteúdo estável. O namespace observado
é explicado por `fs/Makefile:9`, que expande ANDROID_GKI_VFS_EXPORT_ONLY para
`VFS_internal_I_am_really_a_filesystem_and_am_NOT_a_driver`; o loader anterior
declara esse import em `loader.c:1047`. Não é validação de um novo backend.

Abrir arquivo regular com O_NOFOLLOW, como em `qkx_open`, não proíbe outro writer
de alterar o conteúdo. I/O síncrono não transforma um timeout do host em término
remoto comprovado. Digest de origem, readback, selagem e PoC permanecem distintos.

Todos os arquivos devem ser consumidos antes de suspender dependências de I/O.
A ordem do trace host (boundary, clean, descrição de entrada) não valida que
os helpers e mappings sejam utilizáveis nessa fase real. CFI, SCS/x18, Full LTO,
MODVERSIONS, estado MMU, CPUs, DMA/SMMU, watchdog, QMP e logs continuam exigidos.

## Resultado por obrigação

| Obrigação | Resultado desta revisão |
|---|---|
| Protótipos e pares CMA/buddy | Identificados no fonte e exports; sem chamada/build novo |
| Identidade/capacidade/lifetime reais | Não demonstrados; Image continua pedindo todos os 32 MiB nominais |
| Mapping writable, aliases e exclusão de writers/DMA | Não demonstrados |
| Streaming estável/selagem/readback | Contrato e modelo host apenas; nenhum leitor/writer novo |
| Publicação até PoC importável e adequada à fase | Helpers internos encontrados, imports diretos ausentes; solução não escolhida |
| Entrada sem cópia/CFI e shutdown/logs | Não implementados/validados |

**Revisão concluída; nenhum gate runtime liberado.** Próximo passo seguro é
revisar alternativas de publicação de cache e o ponto exato de irreversibilidade
no fluxo existente, somente no host, antes de propor qualquer adaptador.
Não há autorização nova para dispositivo, alocação ou reutilização de consultas
anteriores. Controlador permanece desarmado; monitor/âncora continuam bloqueados.

Evidências e hashes em `private-diagnostics/direct-staging-stock-abi-review-01/`,
incluindo snapshots dos fontes, configs/exports, matriz e suíte. Arquivos
anteriores de evidência e candidatos preservados.
