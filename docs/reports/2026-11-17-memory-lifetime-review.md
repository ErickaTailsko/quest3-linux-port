# Lifetime dos metadados — revisão antes de ampliar a sondagem

**Os 13 descritores foram localizados, mas o contrato de lifetime de uma
varredura de PFNs ainda não está demonstrado.** A revisão encontrou um caminho
vendor de remoção de subseções que não usa as notificações normais de offline.
Não foi preparada/carregada nova sonda, escolhido destino ou executada nova
operação ADB, pausa de CPUs ou aquisição de páginas nesta etapa.

## Evidências usadas

- Fonte pública fixada `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`.
- Configuração já capturada no boot da consulta, conferida por hash contra
  `quest3/configs/stock-device.config`.
- Tabela stock fornecida e listagem /proc/modules já preservada na consulta;
  não foi feita nova leitura do aparelho para esta revisão.
- Resumo com hashes dos fontes/config e matriz de exports:
  `quest3/restart-backend-design/memory-lifetime-audit.json`.

Isso é auditoria do fonte público e de evidências anteriores, não demonstração
de equivalência binária completa ou reprodução de uma corrida no Quest.

## Locks e APIs

`mm/memory_hotplug.c` define o rwsem `mem_hotplug_lock`. Leitores usam
get_online_mems/put_online_mems; o escritor em mem_hotplug_begin toma primeiro
**cpus_read_lock** e depois o lado exclusivo de mem_hotplug_lock.

Na tabela stock fornecida:

| Interface | Exportada | O que não permite concluir |
|---|---|---|
| get_online_mems / put_online_mems | não | Não há ligação tipada direta dessas funções para este módulo |
| mem_hotplug_begin / mem_hotplug_done | não | Não usar endereço privado para contornar isso |
| lock_device_hotplug / unlock_device_hotplug | não | Não substituir por referência ao objeto device |
| cpus_read_lock / cpus_read_unlock | sim | Leitor CPU não exclui escritor de memória, que também toma leitor CPU |
| walk_iomem_res_desc | sim | Callback recebe recurso copiado, não lock sobre memmap/PFNs |
| register_memory_notifier / unregister_memory_notifier | sim | Não cobre toda operação vendor ou uma operação já em andamento |
| stop_machine | sim | Pausa de tarefas não é posse e exige revisão própria do callback e estados possíveis |

Em `kernel/resource.c:find_next_iomem_res`, o recurso é copiado sob
resource_lock e o lock é liberado antes do callback do walker. Resource-lock
não deve ser interpretado como trava de lifetime da página ou do vmemmap.

## Caminho vendor que precisa entrar na prova

Stock tem MEMORY_HOTPLUG e MEMORY_HOTREMOVE habilitados, SPARSEMEM_VMEMMAP,
HOLES_IN_ZONE e HAVE_ARCH_PFN_VALID. QCOM_MEM_BUF e QCOM_MEM_BUF_DEV são módulos.
`mem_buf`, `mem_buf_dev` e `gh_rm_drv` aparecem na listagem já preservada.
Isso **não prova que uma remoção foi chamada ou que uma janela de interesse
seja alvo desses módulos**.

O caminho normal `offline_pages` passa por mem_hotplug_begin, isola/migra
páginas e chama memory_notify(MEM_GOING_OFFLINE). Já:

```text
mem_buf_unmap_mem_s1(sgl)
  -> remove_memory_subsection(nid, base, size)
     -> mem_hotplug_begin()
     -> arch_remove_memory(...)
     -> memblock_remove(...) quando configurado
     -> release_mem_region_adjustable(...)
     -> mem_hotplug_done()
```

O rollback de mem_buf_map_mem_s1 também chama remove_memory_subsection.
A implementação de remove_memory_subsection nesta árvore **não chama
offline_pages, offline_mem_sections ou memory_notify**. Portanto, registrar
um notifier não é prova de exclusão de toda remoção suportada pelo fonte.
Mesmo no caminho normal, registrar o notifier depois de uma notificação já
aprovada não retroativamente para a operação inteira. Vetar notificações
também alteraria a política de hotplug; não seria diagnóstico passivo.

ZONE_DEVICE desabilitado não elimina esse caminho vendor, que chama os helpers
de subseções diretamente. Para restringir uma futura análise à RAM de boot,
é necessário demonstrar os limites e a propriedade dos intervalos nos
chamadores/SG lists, não presumir isso pelo nome System RAM no iomem.

## Validade, RCU e pausa não são intercambiáveis

- pfn_to_online_page verifica seção online e pfn_valid_within; nesta config,
  pfn_valid_within usa pfn_valid. O resultado é uma checagem, não uma referência
  adquirida que mantenha o mapeamento vivo entre checagem e uso concorrentes.
- `mm/sparse.c:section_deactivate` invalida metadados e pode liberar/depopular
  vmemmap. O kfree_rcu do objeto usage não é, sozinho, uma garantia de que todo
  struct page fique mapeado durante qualquer leitor RCU. Não adotar RCU como
  substituto universal da exclusão de hotplug sem prova de todos esses caminhos.
- No caminho normal, online_pages_range só marca seções online após inicializar
  as páginas, e __offline_isolated_pages limpa online antes de retirar páginas.
  Essa ordem ajuda a revisar um snapshot sob pausa, mas não dispensa a revisão
  das subseções vendor e dos estados em que uma tarefa pode ser interrompida.
- stop_machine impede progresso normal das tarefas participantes durante RUN.
  Não se deve esperar por um lock mantido por uma tarefa que ficou pausada.
  Orçamento de callback não garante que uma aquisição bloqueante termine.
- O campo zone obtido de uma página tampouco torna seguro adquirir seu lock
  após uma checagem concorrente se o lifetime da própria página não foi mantido.

A amostra antiga de 13 cabeças permanece uma observação histórica válida no
seu escopo. Não há evidência de que ela tenha corrido contra hot-remove. O que
não está demonstrado é generalizar seu contrato para uma varredura de todos
os PFNs ou para outras regiões/caminhos, nem reusar tipos após os CPUs retomarem.

## Aquisição não pode ser usada como teste passivo

`alloc_contig_range` vendor tem cinco argumentos. Antes de isolar pageblocks,
já lê page_zone(pfn_to_page(start)); chamar essa função não substitui a prova
de que o intervalo é válido e tem lifetime adequado para a chamada. A operação
modifica isolamento, migração e alocação; permanece fora do escopo autorizado.
Um snapshot MOVABLE não concede posse nem exclui mapeamentos DMA antigos.

## Modelo host e decisão

`quest3/restart-backend-design/test-memory-lifetime.py` enumera interleavings
abstratos de checagem/uso e invalidação/liberação:

- Sem exclusão: 70 ordens, com contraexemplo check → remoção → uso.
- Leitores CPU compartilhados: 70 ordens, também com contraexemplo.
- Notifier com veto futuro: 39 ordens, incluindo operação aprovada antes do
  registro e removendo o objeto depois da checagem.
- Leitor de memória mantido até o uso versus escritor exclusivo: duas ordens
  completas admissíveis, sem acesso inválido **nesse modelo**.

O teste também distingue snapshot de posse/DMA e o bloqueio ao esperar lock
de um proprietário pausado. Não executa código de hotplug real, não reproduz
uma corrida no kernel e não prova que um lock privado possa ser usado.
Suíte host: **37 aprovações, zero falhas ou testes ignorados**.

**Decisão:** manter o protótipo simples recusando hotplug e não expandir a
sonda stop_machine ainda. O próximo contrato precisa demonstrar exclusão ou
estabilidade dos metadados para todos os caminhos aplicáveis à janela exata,
incluindo as subseções vendor, sem resolver símbolos privados. Depois disso,
definir um escopo pequeno, tempo/saídas/cleanup e pedir autorização específica
para qualquer pausa de CPUs. Não há nova proposta operacional pronta nesta etapa.
