# Planejamento offline de memória fora da janela fixa

**Resultado: nove intervalos históricos têm geometria para 40 MiB, mas nenhum
é um destino adquirido ou validado.** O ADB não encontrou aparelho conectado
nesta etapa. Não houve carga de módulo, pausa de CPUs, aquisição de páginas,
alteração do loader ou tentativa de boot.

## Entradas e procedência

- DT: `private-diagnostics/pmsg-same-boot-01/live.dtb`.
- Iomem: `private-diagnostics/memory-feasibility-01/iomem.txt`.
- Hashes/tamanhos/retornos conferidos contra os manifestos das capturas.
- Tokens de boot dos registros preflight do DT, baseline PMSG, snapshot
  antes/depois e coleta de memória antes/depois coincidem. Tokens não publicados.

Isso associa os registros ao mesmo **boot histórico**, não cria um snapshot
atômico nem valida o boot atual. O DT binário não contém um boot ID intrínseco.
A amostra stop_machine posterior pertence a outro boot; seus tipos de blocos
não são transferidos para estes intervalos.

## Método e resultado

`tools/plan-memory-survey.py` intersecta memória do DT com System RAM do iomem,
subtrai reservas estáticas do DT, memreserve, todos os recursos não-System RAM
e a janela antiga `[0x90000000,0x93400000)`. Alinha para dentro em blocos de
4 MiB e mantém somente intervalos com pelo menos 40 MiB, conforme o plano
relativo trim2. Usa endereços de 64 bits, sem truncar bancos altos.

| Início | Fim exclusivo | Extensão geométrica |
|---|---|---:|
| `0x82800000` | `0x88c00000` | 100 MiB |
| `0x93400000` | `0xa8000000` | 332 MiB |
| `0xaac00000` | `0xafc00000` | 80 MiB |
| `0xb0000000` | `0xb6800000` | 104 MiB |
| `0xb8000000` | `0xbf800000` | 120 MiB |
| `0xc7c00000` | `0xd8000000` | 260 MiB |
| `0xdc800000` | `0xe8000000` | 184 MiB |
| `0x800000000` | `0x83ac00000` | 940 MiB |
| `0x840000000` | `0x975800000` | 4.952 MiB |

São 1.768 pageblocks geométricos e 1.687 posições **sobrepostas** de 40 MiB.
Não são contagens de blocos livres, alocações possíveis ou sondagens propostas.
Não executar uma varredura de todas essas cabeças sob stop_machine.

O DT real contém uma tupla de memória vazia em `0xd8800000`. O scanner vendor
`drivers/of/fdt.c:early_init_dt_scan_memory` ignora tamanho zero. O helper
passou a registrar e ignorar somente essas tuplas de memória; reservas `reg`
de tamanho zero continuam recusadas. Também respeita `linux,usable-memory`
quando presente e recusa mapas zerados, overflow e endereçamento não suportado.

## Reservas dinâmicas não resolvidas

Há 13 nós com `size`, mas sem `reg`: linux,cma, user_contig_region,
qseecom_region, qseecom_ta_region, cdsp_eva_region, adsp_heap_region,
secure_cdsp_region, sp_region, va_md_mem_region, audio_cma_region,
non_secure_display_region, cnss_wlan_region e mem_dump_region.

Seus nomes/tamanhos no DT não localizam o intervalo efetivamente reservado.
Alguns recursos podem estar refletidos no iomem, mas não foi demonstrada uma
correspondência completa. O resultado mantém `reservation_geometry_complete=false`.
Os intervalos podem conter CMA, páginas ocupadas/UNMOVABLE, limites de zonas,
PFNs inválidos e mapeamentos DMA. Nem mesmo MOVABLE provaria aquisição possível.

## Reprodução e próximos limites

```sh
python3 tools/test-memory-survey.py
python3 tools/plan-memory-survey.py \
  --dtb private-diagnostics/pmsg-same-boot-01/live.dtb \
  --iomem private-diagnostics/memory-feasibility-01/iomem.txt
```

As entradas brutas permanecem privadas. Resultado geométrico e resumo revisado
de procedência: `quest3/restart-backend-design/historical-survey-geometry.json`.
O bloco de procedência foi acrescentado após comparar os registros privados;
o planner sozinho calcula geometria/hashes, não confirma boot IDs.

Suíte host: **33 aprovações, zero falhas ou testes ignorados**. Inclui regressões
para a tupla vazia real, usable-memory, reservas, janela antiga, bancos de
64 bits, redaction e overflow. Não substitui validação no aparelho.

Próximo passo depende de reconectar o Quest ao ADB para uma coleta **somente
leitura**, com DT/iomem/zoneinfo/pagetypeinfo e boot antes/depois correspondentes.
Revisar como localizar reservas dinâmicas com interfaces já disponíveis, sem
presumir que o DT vivo recebeu os endereços escolhidos durante o boot.
Depois, definir um escopo pequeno de sondagem, sincronização/lifetime, limites
de duração e cleanup; qualquer nova pausa de CPUs exige revisão e autorização
próprias. Esta análise não autoriza aquisição, migração ou sobrescrita de RAM.

Nenhuma base física, lista operacional de endereços ou comando de aquisição foi
gerado. Layout fixo e bloqueios CFI/CPUs/DMA/logs permanecem inalterados.
