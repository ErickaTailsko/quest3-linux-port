# Traços do contrato direto — modelo somente host

**65 grupos host aprovados, zero falhas/ignorados.**
`quest3/layout-review/direct_staging_trace.py` verifica tuplas imutáveis de
eventos fictícios. Não despacha os nomes dos eventos: não há alocador, reader,
writer, callback, comando no Quest, operação de cache ou integração no loader.

O modelo formaliza parte do
[contrato documental](2026-11-18-direct-staging-contract-review.md), sem provar
que seus requisitos estão satisfeitos no alvo.

## Dados e limites

- Três `Segment` tipados: Image/initrd/DT, comprimento de arquivo positivo e
  staging page-rounded. Teto numérico de 32 MiB Image e 2 MiB por auxiliar.
- Offsets **relativos ao payload**, nunca endereços físicos ou VA. Prefixo
  text_offset e padding externo ao staging não entram nos intervalos.
- `Event` tipado vinculado a boot/attempt fictícios distintos; no máximo 65.536
  eventos. Buffer declarado de 4 KiB a 2 MiB, page-aligned. Não é buffer alocado.
- Claims de fase são nomes exatos de obrigações, sem duplicatas/extras/faltas.
  Dizer `real-handles-retained-including-transition` não cria nem verifica handle.

Esses bounds não substituem `returned_layout.py`: não há parsing de header/DT,
escolha de bases, validação de conteúdo, providers reais ou revisão de aliases
físicos neste novo módulo. Geometria, snapshots e traços continuam separados.

## Ordem de eventos aceita na hipótese

1. `prepare`: exige claims de consentimento, contexto/fontes estáveis, recursos
   completos, CMA/lifetime, layout/chosen, mappings, isolamento e I/O/logs.
2. `read-request`: um único pedido global; offset igual aos bytes já copiados,
   tamanho positivo limitado pelo buffer e restante de arquivo.
3. `read-complete`: deve corresponder ao pedido. Retorno positivo curto deixa
   disponíveis apenas os bytes realmente declarados. Zero antes do fim é EOF
   precoce e termina como falha; retorno maior que o pedido é recusado.
4. `copy-complete`: só pode declarar cópia exata do buffer completo disponível.
   Não permite copiar antes da conclusão nem reutilizar buffer/pedir outra leitura
   enquanto seus bytes ainda esperam cópia. Não realiza a cópia.
5. `zero-complete`: somente depois do arquivo completo, sem pedido/buffer pendente,
   começando exatamente no próximo byte de zero-fill e sem exceder buffer/range.
6. `seal`: exige arquivo e zeros completos em todos os segmentos, nenhum pedido
   ou buffer pendente e claims separados de digest, destino, quiescência/selagem.
7. `irreversible-boundary`: exige selagem e claims globais de shutdown/CFI/logs.
8. `final-clean`: exige boundary e claims de PoC, cobertura de linhas, publicação
   de transição/I-cache e estado arquitetural/barreiras.
9. `entry-described`: exige clean e claim de caminho dedicado sem cópia. Termina
   o **traço descritivo**, não executa entrada nem retorna permissão para isso.

O modelo escolhe clean final depois do boundary para exercer uma hipótese de
ordenação. Não valida a sequência arquitetural nem afirma que todas as operações
necessárias sejam viáveis nessa fase no Quest. Readback/selagem e PoC continuam
obrigações distintas. Nenhuma escrita é aceita depois de selagem ou clean;
não há invalidar a selagem e reabrir staging automaticamente.

## Falhas e incerteza

Todos os estados abaixo são terminais e recusam **qualquer** evento seguinte,
incluindo reads, cleanup, retry, fallback, prepare e resume:

| Estado | Significado de fixture |
|---|---|
| `FAILED_RETAINED` | Erro conhecido antes do boundary: I/O, conteúdo, mapping/handle, writer externo ou release; também EOF precoce |
| `FAILED_AFTER_IRREVERSIBLE` | Erro conhecido depois do boundary, sem caminho ordinário de abort/rollback |
| `FROZEN_UNKNOWN` | Timeout, interrupção, falha de journal, conclusão desconhecida ou restart |

O resultado mantém separadamente se o boundary foi declarado, se há pedido
de leitura sem conclusão declarada e quantos bytes de buffer esperam cópia.
EOF é conclusão conhecida da leitura, mas não completa o payload e não permite
continuar. Retenção aqui é classificação conservadora de design, não posse real.
Não há API de release e nenhum estado autoriza unload/cleanup.

Prefixos válidos são aceitos como **prefixos**, não como operações concluídas.
Um prefixo encerrado após request, por exemplo, ainda declara leitura pendente.
Um reinício não é recuperável por replay: o evento restart congela o traço, e
reapresentar uma tupla antiga não prova a história nem os recursos atuais.

## Testes e limite de confiança

`test-direct-staging-trace.py` cobre:

- Traço completo e todos os prefixos; leituras curtas e contabilidade de zeros.
- Remoção de cada evento obrigatório e de cada claim; claims extras/duplicados,
  contexto diferente, tipos/ranges inválidos e limites de buffer/eventos.
- Cópia antes de read-complete, reutilização do buffer, conclusão substituída,
  EOF precoce, zero-fill antecipado/incompleto e operações depois de seal/clean.
- Cada motivo de falha/incerteza em cada prefixo não terminal, seguido de
  tentativas de leitura/cleanup/retry/fallback/resume e outras operações.
- 50 traços completos com chunks curtos seeded, incluindo arquivo multipágina,
  zero-fill multipágina e segmento sem tail; 500 permutações seeded para exercitar
  recusa de ordem inválida. Isso não é model checking exaustivo.
- Replay de clones idênticos produz o mesmo resultado, explicitamente sem prova
  de lifetime, independência, estado físico ou execução histórica.

Mesmo `ENTRY_DESCRIBED` mantém **falsos** ownership, autorização verificada,
target readback, cache verificado, streaming/writer implementados, integração,
execução, cleanup, retomada e boot_ready. Claims podem ser inteiramente falsas
no mundo real; aprovação do traço só demonstra consistência com essas regras.

## Resultado e próximo gate

O modelo de traços e um novo grupo de regressões estão implementados no host.
Não há novo caminho operacional, destino adquirido, build Android/kernel,
transferência ou operação no Quest. Proteções e artefatos anteriores preservados;
a hipótese de memória continua ~68,63 versus ~36,02 MiB, não pico medido, e a
solicitação Image CMA continua 32 MiB.

Próximo gate: confrontar **offline** as obrigações com fontes/ABI stock e
primitivas de mapping/cache disponíveis, registrando lacunas antes de propor um
adaptador. Isso não inclui writer, transição nova ou mudanças do loader. Qualquer
experimento no aparelho exige nova autorização específica; monitor/âncora e
gates de shutdown, DMA/SMMU, CFI, QMP, watchdog e logs continuam bloqueados.

Evidências em `private-diagnostics/direct-staging-traces-host-01/`: código,
testes/logs, traço sintético completo e casos terminais, resultados e hashes.
