# Mapas de memória — primeira coleta pelo novo controlador no Quest

**Atualização posterior no mesmo boot:** os 13 descritores dinâmicos foram
localizados por consulta única autorizada, sem pausa de CPUs e com cleanup.
[Resultado](2026-11-17-reserved-descriptor-result.md). A pendência de bases
neste relato descreve o estado anterior à consulta, não o resumo atual.

**Coleta somente leitura aprovada no aparelho.** Dez leituras terminaram com
retorno zero e stderr vazio; hashes/tamanhos de stdout e stderr foram
recalculados e conferidos. Boot IDs válidos e iguais antes/depois.

Não houve escrita solicitada no dispositivo, push, carga de módulo, pausa de
CPUs, reserva/migração de páginas, alteração de serviços ou reset. Foi usado o
`su` existente, sem instalação ou nova tentativa de obter root.

## Procedência e artefatos

Coleta iniciada em 2026-11-17 às 10:19:33 UTC, kernel
`5.10.246-gd7102a837402`, identidade root, páginas de 4 KiB,
pageblock_order=10 e 1.024 páginas/bloco confirmados.

Brutos privados: `private-diagnostics/memory-maps-20261117T101933Z/`.
Resultado revisado: `quest3/restart-backend-design/memory-map-capture-2026-11-17.json`.
Serial, valores de boot ID e DT bruto não foram acrescentados à publicação.

| Arquivo | Bytes | SHA-256 |
|---|---:|---|
| DT | 698.964 | `7b377234c27f8c4c0d3ba8f48a1502e5aaff5f85ec476d8e90dc4ca22aca5077` |
| iomem | 8.645 | `773fea1c2921d02146f4a1193730970415c4b487d5eed6dda69ae1cfa9f9ff57` |
| zoneinfo | 4.188 | `cbe69905cca30ff5147eaad5606c86411e70130c1993f0ede7593e41834f7482` |
| pagetypeinfo | 1.936 | `2279e81d311a163abf9a0f5c3866cc13fed26159b044201d696c72be876d5fc4` |

Este boot é diferente tanto da captura histórica DT/iomem/PMSG quanto da
amostra stop_machine anterior. Não se inferiu causa, momento ou número de
resets intermediários. Os tipos observados anteriormente em endereços físicos
específicos **não foram revalidados** por esta coleta.

O DT atual não é byte a byte igual ao histórico; a comparação semântica
encontrou mudança de nome/endereço de nó RPC do hypervisor. Não transportar
automaticamente propriedades dinâmicas de um boot para outro. Iomem é idêntico
ao histórico, o que não torna os mapas de ocupação ou migratetypes idênticos.

## Geometria recalculada, não destinos livres

O planner offline aceitou o novo DT/iomem e produziu os mesmos nove intervalos
do [planejamento anterior](2026-11-17-memory-survey-planning.md): 1.768
pageblocks geométricos, com 1.687 posições sobrepostas de 40 MiB. Nenhuma
posição foi escolhida como base, sondada ou adquirida.

As 13 reservas dinâmicas continuam sem `reg` no DT capturado. A localização
efetiva de todas elas não foi estabelecida; `reservation_geometry_complete`
permanece falso. A coleta bem-sucedida remove o bloqueio de **falta de mapas
correspondentes novos**, não o bloqueio de posse da RAM.

## Zonas e limites

| Zona | Span observado, fim exclusivo | Páginas presentes / spanned |
|---|---|---:|
| DMA | `[0x80000000,0x100000000)` | 505.856 / 524.288 |
| Normal | `[0x100000000,0x980000000)` | 1.559.808 / 8.912.896 |

DMA32 e Movable têm span zero nesta captura. O nome da zona Movable não é
sinônimo do migratetype MOVABLE, que também existe nas zonas DMA/Normal.
Os spans têm buracos; não usar seus limites como prova de validade de cada PFN.
Os bancos altos dos intervalos geométricos ficam dentro do span Normal, mas
isso não demonstra contiguidade física elegível ou suporte do loader a eles.

Pagetypeinfo fornece totais por zona e tipo, não os endereços dos pageblocks.
Mesmo no mesmo boot, os dados foram lidos separadamente, sem congelar o
alocador. Não são snapshot atômico, validação de lifetime ou exclusão de DMA.
O trecho MOVABLE de 24 MiB citado em relatórios anteriores continua sendo
**uma observação histórica**, não um limite demonstrado para este boot.

## Próximo trabalho permitido e bloqueios

Revisar offline a localização/visibilidade das reservas dinâmicas e as
interfaces stock disponíveis antes de propor uma sondagem pequena e limitada.
Não generalizar o controlador antigo para varrer os 1.768 blocos. Qualquer
nova pausa de CPUs requer plano revisado e autorização próprios; aquisição
de páginas não faz parte da coleta e também não foi autorizada por ela.

Nenhuma alteração nos candidatos, layout fixo ou bloqueios de handoff CFI,
CPU_OFF, DMA/SMMU, QMP herdado e captura dos logs finais. Nenhum segundo kernel
iniciado. Suíte host reexecutada: **34 aprovações, zero falhas/ignorados**.
