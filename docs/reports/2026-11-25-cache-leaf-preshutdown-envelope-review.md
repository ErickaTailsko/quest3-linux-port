# B0 — envelope e seção pré-shutdown

Revisão documental offline do
[draft de geometria](2026-11-23-cache-leaf-explicit-geometry-abi-draft.md).
Draft não adotado; B0 PENDING. Sem candidato, build, operação de CPU/cache ou
acesso ao Quest.

## Caminho público de estabilização: hipótese delimitada

`kernel/cpu.c:300–327` usa `cpu_hotplug_lock`, um percpu rwsem:
`cpus_read_lock()` adquire leitura; `cpus_read_trylock()` tenta aquisição;
`cpus_read_unlock()` libera. Os caminhos `_cpu_down()` (1059/1071) e `_cpu_up()`
(1520/1526) adquirem escrita. A tabela stock fornecida registra:

| Interface | CRC | Provider / export |
|---|---|---|
| cpus_read_lock | 0xa04f945a | vmlinux / EXPORT_SYMBOL_GPL |
| cpus_read_trylock | 0x5831e062 | vmlinux / EXPORT_SYMBOL_GPL |
| cpus_read_unlock | 0x18fb2caf | vmlinux / EXPORT_SYMBOL_GPL |

Nenhuma possui namespace declarado nessa tabela. Presença/export/CRC não
comprovam contexto seguro de chamada ou relação integral com o binário runtime.

Hipótese para revisão futura: seção pré-shutdown em contexto permitido, com
aquisição bem-sucedida antes da consulta da geometria e liberação apenas após
conclusão da manutenção. Não basta consultar sob lock e operar depois de soltá-lo.
Isso depende da cobertura de todos os caminhos de atualização e de ordem de
locks; esta leitura não constitui prova completa de ausência de corrida.

Não adquirir esse lock no leaf; não segurá-lo através de CPU shutdown, freezer,
callbacks de plataforma ou transição. Não chamar API potencialmente bloqueante
de contexto atômico. Trylock falhando deve recusar antes de manutenção; não
autoriza espera/retry infinito nem reutilização de geometria antiga.
Não foi escolhido nem implementado um protocolo de aquisição.

O lock não fixa automaticamente o caller numa CPU, não retém mappings/memória,
não exclui DMA/writers e não prova que nenhuma linha mudou após sua liberação.
Uma limpeza nessa seção não cobre escritas posteriores nem prova publicação
final no ponto de handoff. O caminho pós-shutdown segue fora desse contexto.

## Envelope: por que ainda falta prova de G

`asm/assembler.h:395–429` seleciona operação por alternatives para certos
cleans, arredonda início com a linha fornecida pelo macro e termina com DSB
parametrizada. `arch/arm64/mm/cache.S:99–111` usa `civac, sy` no helper privado
de flush. Esses são precedentes locais, não APIs exportadas para transplantar.
Não copiar sequences, dependências privadas ou flags de exceção.

O passo S sanitizado é uma hipótese para cobertura. Para containment de efeitos
é necessário demonstrar G para a operação, atributos e CPUs efetivos. O máximo
de cacheinfo/CWG não ganha esse significado apenas por ser maior que S.
Também não adotar um limite como 128/256 por familiaridade com ARM64.

Uma possível simplificação futura seria trabalhar somente em extensões próprias
alinhadas a G e manter todas as linhas de borda dentro delas. Isso só é útil
depois de provar G; alinhamento de página ou um allocator não prova sozinho
granularidade dos efeitos. Distinguir propriedade da extensão inteira de
propriedade apenas dos bytes do payload.

Permanecem em aberto a escolha arquitetural de operação/barreiras, erratas,
efeitos de borda, relação entre CPU/cache levels e mappings, e o vínculo de
contexto até o uso. Não há implementação aprovada de S/G.

## Disposição

Há interfaces públicas para estudar exclusão de hotplug numa seção limitada.
Isso não fecha B0 nem a publicação final de cache. Próximo gate: demonstrar
G/operação e ordem de locks/contexto dessa seção; se não houver evidência,
manter PENDING. Nenhuma mudança nos verificadores ou no contrato v1.
Progresso permanece ~40% subjetivo.
