# Procedência da RAM — limites de sysfs e cobertura por seção

**As interfaces revisadas não distinguem com segurança RAM de boot de uma
importação já adicionada, nem mantêm o lifetime dos PFNs.** O cruzamento dos
nove intervalos geométricos encontrou 60 seções: 56 com cobertura integral
por recursos System RAM e quatro com buracos no snapshot. Isso não habilita
sondagem nem seleciona destino.

Foi uma análise offline do fonte fixado e dos mapas já preservados. Nenhum
novo comando ADB, coleta extensa de processos/buffers, módulo, tracing, escrita
em state/online, pausa de CPUs, aquisição ou reset foi executado.

## 1. O atributo removable não é um teste de elegibilidade

`drivers/base/memory.c:removable_show` é explicitamente tratado pelo fonte como
interface legada e heurística ruim. Ele retorna apenas
`IS_ENABLED(CONFIG_MEMORY_HOTREMOVE)`. A configuração capturada tem essa opção
habilitada: ler 1 não comprova que um bloco possa efetivamente ser removido,
que esteja livre ou que pertença a um caminho específico.

state e phys_index identificam estado/topologia do objeto memory_block, não
uma referência que estabilize todas as páginas de seu span. Manter aberto um
arquivo sysfs ou uma referência ao device não equivale a get_online_mems.
O caminho vendor add/remove_memory_subsection também não cria/remove objetos
memory_block da mesma forma que o hotplug normal completo. A mera presença
de um objeto memoryN não inventaria cada importação de subseção.

## 2. Estatísticas DMA-BUF não são um inventário de SGLs

Stock tem CONFIG_DMABUF_SYSFS_STATS habilitado, mas os atributos definidos em
`drivers/dma-buf/dma-buf-sysfs-stats.c` são exporter_name e size. Não fornecem
ipa_base, PFNs, SGL nem identidade do memparcel.

A criação dessas entradas é agendada como work e pode ser omitida quando
somente a referência temporária do worker resta; também há caminhos de erro.
Logo, ausência numa enumeração separada não prova ausência de buffer/importação
durante outra leitura. O número ou nome de exportadores tampouco prova os
intervalos físicos que se pretende excluir.

Além disso, no caminho de alocação remota do fonte, um objeto membuf pode
adicionar memória a um carveout heap antes de existir um DMA-BUF alocado desse
heap. Não há correspondência universal entre a lista de buffers e a lista
de todos os intervalos adicionados. Esse caminho ALLOC depende do bit CONSUMER;
o DT supplier observado limita sua aplicabilidade, mas não transforma stats
em prova de que o caminho RETRIEVE esteja inativo.

Por isso não foi feita uma coleta ampla de estatísticas que não contêm os
campos necessários, nem uma enumeração de FDs como substituto da prova.

## 3. Rótulo/flags do recurso não identificam sua origem

Os dois construtores revisados usam o nome System RAM e flags SYSTEM_RAM |
BUSY: request_standard_resources em `arch/arm64/kernel/setup.c`, para RAM do
memblock inicial, e register_memory_resource em `mm/memory_hotplug.c`, para
memória adicionada posteriormente.

O walker tipado de recursos devolve cópia de limites/flags/descritor/parent;
não inclui um carimbo de criação que identifique univocamente a origem boot.
Parent pode distinguir algumas topologias, mas uma importação no nível raiz
também pode ter os mesmos campos relevantes de um recurso inicial. Só observar
esse recurso depois de criado não recupera sua história nem mantém o lock
de hotplug sobre o memmap.

Assim, preparar outro módulo que apenas repita esse walker **não fecharia
a prova de procedência/lifetime**. Nenhum módulo adicional foi preparado.

## 4. Cobertura das seções que cruzam os nove intervalos

No fonte/config ARM64 de páginas de 4 KiB, SECTION_SIZE_BITS=27: seções de
128 MiB. Não confundir seção, memory_block, pageblock de 4 MiB e a janela
relativa de payload de 40 MiB.

`tools/analyze-section-coverage.py` cruza os nove intervalos com a união dos
recursos System RAM do iomem correspondente, contando cada seção uma vez.
Recursos reserved filhos de System RAM **não** são subtraídos nessa contagem:
o teste de cobertura do caminho normal offline_pages usa System RAM, não a
mesma lista de exclusões de posicionamento do payload.

| Seção com buracos, fim exclusivo | Bytes sem System RAM no mapa |
|---|---:|
| `[0x80000000,0x88000000)` | 25.976.832 |
| `[0x88000000,0x90000000)` | 75.505.664 |
| `[0xd8000000,0xe0000000)` | 74.448.896 |
| `[0x838000000,0x840000000)` | 53.477.376 |

As outras 56 seções cruzadas têm cobertura integral no snapshot. Não se
conclui que sejam removíveis: zona, páginas ocupadas, isolamento e outras
condições ainda se aplicam.

Para as quatro com buracos, a prechecagem normal de offline_pages rejeitaria
um intervalo que as inclua **se o mapa observado fosse o usado pela operação**.
Isso é uma restrição pontual, não imunidade permanente. Não foi demonstrado
que os buracos não possam mudar, e remove_memory_subsection não passa por
essa prechecagem normal. O resultado tampouco valida os struct page de cada
PFN ou as permissões stage-2.

Nenhuma seção/posição foi classificada ou ranqueada como destino seguro.
Resultado revisado: `quest3/restart-backend-design/section-coverage-result.json`.
As hipóteses de tamanho de seção vêm do fonte/config revisados, não de uma
nova medição runtime de memory_block_size_bytes nesta etapa.

## Reprodução e decisão

```sh
python3 tools/analyze-section-coverage.py \
  --iomem private-diagnostics/memory-maps-20261117T101933Z/iomem.txt \
  --geometry quest3/restart-backend-design/memory-map-capture-2026-11-17.json
python3 tools/test-section-coverage.py
```

Testes sintéticos cobrem bancos de 64 bits, bordas, buracos fora da subjanela,
recursos filhos/duplicados, mapas inválidos/ocultados, overflow e limites da
análise no host. Todos os gates de imunidade/lifetime/posse permanecem falsos.
Suíte host: **39 aprovações, zero falhas ou testes ignorados**.

O requisito restante não é obter mais um total de páginas ou mais uma cópia
do mesmo iomem. É estabelecer exclusão de remoção ou estabilidade comprovada
para os metadados da janela exata, incluindo os caminhos aplicáveis, com
interfaces tipadas compatíveis com stock. Sem isso, não ampliar a sonda nem
pedir uma pausa de CPUs como se a revisão já estivesse concluída. A localização
dos 13 descritores CMA continua válida no escopo do boot capturado e não foi
repetida; posse e DMA permanecem bloqueios independentes.
