# Reservas dinâmicas — inventário e bloqueio de localização

**Atualização:** após esta auditoria, a consulta única autorizada por módulo
localizou os 13 descritores, com cleanup confirmado no mesmo boot.
[Resultado atual](2026-11-17-reserved-descriptor-result.md). O estado sem
autorização/módulo/endereço abaixo registra a etapa histórica desta auditoria.

**As bases físicas ainda não foram localizadas.** Foram identificados os 13
descritores dinâmicos, seus tamanhos, restrições e consumidores. As interfaces
de leitura existentes no Android não forneceram os endereços nesta etapa.
Não propor uma nova sondagem de pageblocks com esses endereços ainda ausentes.

## Evidência adicional, somente leitura

Coleta em 2026-11-17 às 10:24:18 UTC, com `su` existente e boot conferido
antes/depois, igual ao da coleta de mapas das 10:19:33 UTC. Foram lidos release,
identidade, uptime, mounts, config.gz, dmesg e listagens de interfaces/pstore.
Hashes e comprimentos dos arquivos e stderr foram recalculados e conferidos.
Nenhum mount, módulo, mudança de configuração, conteúdo de RAM física,
alocação/migração ou reset foi solicitado.

Brutos: `private-diagnostics/dynamic-reservations-20261117T102418Z/`.
Inventário revisado: `quest3/restart-backend-design/dynamic-reservation-inventory.json`.
Não publicar automaticamente os brutos, serial ou valores de boot ID.

## O que o DT permite afirmar

Os 13 nós declaram `shared-dma-pool` e `reusable`, sem `no-map`; são pedidos
de pools CMA. Nenhum deles ganhou `reg` no FDT capturado.

| Nó em /reserved-memory | Tamanho pedido | Restrição de alocação |
|---|---:|---|
| linux,cma | 32 MiB | abaixo de 4 GiB |
| user_contig_region | 16 MiB | abaixo de 4 GiB |
| qseecom_region | 20 MiB | abaixo de 4 GiB |
| qseecom_ta_region | 16 MiB | abaixo de 4 GiB |
| cdsp_eva_region | 4 MiB | abaixo de 4 GiB |
| adsp_heap_region | 12 MiB | abaixo de 4 GiB |
| secure_cdsp_region | 40 MiB | abaixo de 4 GiB |
| sp_region | 16 MiB | abaixo de 4 GiB |
| va_md_mem_region | 16 MiB | a partir de 4 GiB |
| audio_cma_region | 16 MiB | abaixo de 4 GiB |
| non_secure_display_region | 164 MiB | abaixo de 4 GiB |
| cnss_wlan_region | 32 MiB | abaixo de 4 GiB |
| mem_dump_region | 12 MiB | abaixo de 4 GiB |

Soma: **396 MiB**, sendo 380 MiB pedidos abaixo de 4 GiB e 16 MiB no intervalo
alto. Isso coincide com os contadores CMA observados em zoneinfo: 97.280
páginas na DMA e 4.096 na Normal, com páginas de 4 KiB. É uma consistência
agregada, **não uma prova de identidade, inicialização ou endereço de cada pool**.

`alloc-ranges` limita onde procurar durante o boot; não registra a posição
escolhida. O alinhamento pedido é 4 MiB em 12 nós; va_md_mem_region não traz
alinhamento explícito. O caminho CMA do fonte ajusta o mínimo para 4 MiB neste
ambiente. Não reconstruir bases simulando a ordem do alocador: faltam outras
alocações do memblock e o estado efetivo do boot.

Os consumidores por phandle foram cruzados no inventário, incluindo DMA heaps,
QSEE, DSP, display, WLAN e minidump. A ligação `memory-region` também não
fornece endereço físico por si só.

## Por que os endereços não apareceram

- Configuração lida do aparelho: `CONFIG_DEBUG_FS` e `CONFIG_CMA_SYSFS`
  desabilitados. `CONFIG_ARCH_KEEP_MEMBLOCK=y` não cria, sozinho, uma interface
  de usuário para ler a tabela.
- Ausentes: `/sys/kernel/debug/cma`, `/sys/kernel/debug/memblock`,
  `/sys/kernel/mm/cma` e `/sys/firmware/memmap`. Não foi tentado montá-los.
- Mounts mostram tracefs, mas não debugfs. Tracefs não substitui um inventário
  já existente de bases CMA; não foram habilitados eventos ou tracing.
- Pstore está vazio.
- Dmesg tem 320.668 bytes e começa em 8.091,804363 s, chegando a 9.635,961777 s.
  Não há mensagens de criação CMA ou inicialização reserved-memory. A ausência
  num buffer tardio não demonstra que a inicialização falhou.
- A busca nos logs `.txt` anteriores preservados em `diagnostics/` e
  `private-diagnostics/` também não encontrou as mensagens de criação procuradas.

Detalhe do transporte: a listagem de caminhos ausentes veio em stdout e ADB/su
retornou zero. A ausência foi identificada pelo conteúdo, não pelo retorno.
Esse comportamento impede tratar exit zero isolado como leitura bem-sucedida.

## Caminho tipado encontrado, ainda não executado

O fonte fixado oferece `of_reserved_mem_lookup(struct device_node *)`, exportado
GPL na tabela stock fornecida, CRC `0xfece5d03`. A busca de nó por caminho usa
`of_find_node_opts_by_path`, também exportado (`0xebe5690d`). A função procura
o basename na tabela estática `reserved_mem` e retorna um descritor com
`base` e `size`. Não exige kallsyms, kprobe ou acesso físico arbitrário.

Referências do fonte público fixado:

- `drivers/of/of_reserved_mem.c`: alocação em `__reserved_mem_alloc_size`,
  inicialização em `fdt_init_reserved_mem` e consulta em `of_reserved_mem_lookup`.
- `include/linux/of_reserved_mem.h`: layout público do descritor e protótipo.
- `kernel/dma/contiguous.c:rmem_cma_setup`: associa CMA e registra base/tamanho.
- `mm/cma_debug.c`: arquivos base_pfn/count dependem de debugfs.
- `mm/cma_sysfs.c`: a implementação desta árvore expõe contadores, não bases;
  habilitá-la não seria solução pronta, mesmo se fosse permitido mudar o kernel.

**Cuidado:** em falha da inicialização, `fdt_init_reserved_mem` pode liberar a
região sem zerar base/size do descritor. Logo, uma consulta futura não deve
classificar qualquer par não zero como reserva CMA ativa. Deve registrar
presença de ops/priv e quaisquer inconsistências, sem invocar callbacks ou
desreferenciar estruturas privadas. CRC de símbolo não prova sozinho todo o
layout binário interno.

## Limites de uma eventual consulta de descritores

Esta é uma revisão de escopo, **não autorização de carga** e não uma proposta
de sondagem de PFNs/pageblocks. Caso autorizada separadamente:

1. Preparar módulo stock com proteções e verificação de config/CRCs/imports;
   revisar acessos aos campos e manter recusas por ABI/config inesperadas.
2. Fixar os 13 caminhos do inventário, sem parâmetros de endereço arbitrário.
3. Uma consulta de cada descritor, copiando somente nome/base/tamanho e flags
   de presença ops/priv; não invocar ops, atribuir dispositivo, alocar CMA,
   percorrer bitmap, ler conteúdo da reserva ou pausar CPUs.
4. Verificar nomes, tamanho esperado, alinhamento, overflow e alloc-ranges;
   divergência deve ficar explícita e impedir marcar localização confirmada.
5. Preservar boot antes/depois, relatório privado e remoção do módulo/temporários;
   leitura de relatório não deve disparar novas consultas automaticamente.

OF_DYNAMIC e OF_OVERLAY estão desabilitados na configuração lida do aparelho,
mas isso não elimina a necessidade de revisão de lifetime/ABI. Mesmo um módulo
somente leitura executa código no kernel e pode causar falha ou travamento.

Nenhum módulo foi implementado ou carregado nesta etapa. Os 13 endereços
permanecem nulos no inventário; não reduzir a lista de exclusões por inferência.
Sem localização completa, não selecionar destino nem ampliar a sondagem.
