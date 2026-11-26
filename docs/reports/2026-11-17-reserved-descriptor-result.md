# Reservas dinâmicas — 13 endereços localizados no boot observado

**Consulta única autorizada concluída: os 13 descritores passaram nas
verificações. Módulo, sysfs e arquivo temporário foram removidos e a ausência
foi reconferida.** Não houve pausa de CPUs, sondagem de páginas, aquisição de
RAM ou tentativa de boot.

## Recuperação do transporte e execução

Após o usuário informar a reconexão, o boot foi comparado ao registrado antes
do envio interrompido: **é o mesmo boot**. O módulo/sysfs não estavam presentes
e o caminho temporário exato da operação anterior também estava ausente; não
foi necessário removê-lo. A tentativa antiga permanece com zero inserções.

O controlador revisado enviou 270.904 bytes em blocos de 4 KiB, conferiu tamanho
e SHA-256 remotos e executou **um insmod**, com `inspect=1`. O relatório trouxe
13 entradas, `complete=13`, todos os erros zero e presença de ops/priv.
Nomes, tamanhos, alinhamento de 4 MiB, limites alloc-ranges e ausência de
sobreposição foram conferidos no módulo e novamente no host.

O boot é igual ao da coleta DT/iomem usada no planejamento. CPU online antes
e depois: `0-5`. A checagem adicional após cleanup confirmou, com boot antes
e depois, ausência do módulo em /proc/modules, do sysfs e do arquivo temporário.

## Localizações dos descritores

Endereços físicos; fim exclusivo. Não são destinos de payload.

| Nó em /reserved-memory | Base | Fim exclusivo | Tamanho |
|---|---|---|---:|
| linux,cma | `0xfd000000` | `0xff000000` | 32 MiB |
| user_contig_region | `0xf6400000` | `0xf7400000` | 16 MiB |
| qseecom_region | `0xf8400000` | `0xf9800000` | 20 MiB |
| qseecom_ta_region | `0xf7400000` | `0xf8400000` | 16 MiB |
| cdsp_eva_region | `0xe9c00000` | `0xea000000` | 4 MiB |
| adsp_heap_region | `0xe9000000` | `0xe9c00000` | 12 MiB |
| secure_cdsp_region | `0xf9800000` | `0xfc000000` | 40 MiB |
| sp_region | `0xfc000000` | `0xfd000000` | 16 MiB |
| va_md_mem_region | `0x97f000000` | `0x980000000` | 16 MiB |
| audio_cma_region | `0xe8000000` | `0xe9000000` | 16 MiB |
| non_secure_display_region | `0xec000000` | `0xf6400000` | 164 MiB |
| cnss_wlan_region | `0xea000000` | `0xec000000` | 32 MiB |
| mem_dump_region | `0xff000000` | `0xffc00000` | 12 MiB |

Soma: **396 MiB**. Os 12 descritores baixos formam a união contínua
`[0xe8000000,0xffc00000)`, de 380 MiB. No iomem do mesmo boot há exatamente
esse recurso agregado `reserved`. O descritor alto, de 16 MiB, está contido
no recurso `reserved` `[0x97dd46000,0x980000000)`; não se atribui o restante
desse recurso ao mesmo pool.

## Efeito sobre o planejamento

Subtraídos explicitamente os 13 intervalos dos nove intervalos geométricos
anteriores: **nenhuma interseção; os nove permanecem iguais**. As áreas já
estavam fora dos intervalos que sobreviveram às exclusões de recursos/DT e
ao mínimo de 40 MiB. Agora há associação dos nomes às bases dos descritores,
em vez de inferi-las dos totais CMA ou da ordem de alocação.

O helper `plan-memory-survey.py` sozinho continua analisando DT/iomem e
marcando como não resolvidos os nós sem `reg`: ele não importa este relatório
nem consulta o kernel. A resolução dos 13 descritores está no resultado separado
e só é associada a esse boot pela procedência conferida. Não trocar seu campo
de geometria incompleta por uma alegação de RAM livre ou reserva universal.

## Evidências e limites

- Módulo SHA-256: `6ac24447b03474a6343a25fe19871a43b0a9e6f383c2e6301ff7b5803c80d066`.
- Resultado revisado: `quest3/reserved-descriptor-query/device-result.json`.
- Reconexão/fechamento da tentativa antiga:
  `private-diagnostics/reserved-descriptor-reconnect-01/`.
- Consulta e checagem posterior:
  `private-diagnostics/reserved-descriptor-query-02/`.
- O resultado anterior de falha de transporte permanece preservado como
  histórico, não como estado atual da limpeza.

São localizações dos descritores runtime com metadados consistentes; não foi
desreferenciada a estrutura CMA privada ou invocado callback. Presença de
ops/priv evita aceitar descritores obviamente sem setup, mas não prova todo
estado interno do alocador, equivalência binária completa ou segurança DMA.
Nenhum conteúdo de reserva ou PFN foi lido. Metadados não foram capturados
atomicamente. Mudança de boot exige revalidar a procedência, não reutilizar
esses endereços como verdade atual.

O requisito de localizar os 13 descritores foi concluído. Permanecem abertos
elegibilidade/validade dos PFNs, migratetypes atuais, lifetime, posse do destino
e quiescência DMA. **Não foi selecionada base nem proposta/executada nova
sondagem com pausa de CPUs.** A única inserção autorizada foi consumida; não
repetir a consulta automaticamente.

Suíte host reexecutada: **36 aprovações, zero falhas ou testes ignorados**.
