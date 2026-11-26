# Vínculo de layout, fases e cobertura — somente host

**67 grupos host aprovados, zero falhas/ignorados.**
`quest3/layout-review/staging_binding_review.py` compõe três referências locais
numa única timeline de fixtures. Não é backend de staging, controle de acesso,
helper de cache, writer, API de entrada ou integração com o loader.

## O que passa a ser confrontado

1. Reexecutar `returned_layout.plan` sobre Image/initrd/DT fornecidos; exigir
   chosen já preparado. Não reescrever DT silenciosamente.
2. Validar os seis recursos de `cache_publication_plan`: payloads, código,
   PGD/PUD. IDs, bases, tamanhos completos, offsets de payload e staging dos
   três destinos devem coincidir **exatamente** com o layout.
3. Confrontar todos os recursos completos com RAM e reservas estáticas do DT
   fornecido, inclusive código/tabelas. Exclusão mútua/padding continua exigida.
   Reservas dinâmicas continuam não localizadas e explícitas no resultado.
4. Derivar comprimentos dos segmentos de fase a partir do layout/bytes reais de
   input, não aceitar uma segunda geometria de segmentos declarada pelo caller.
5. Projetar os eventos de fase para `direct_staging_trace.review`, preservando
   validação de contexto, progresso bounded, selagem e estados terminais.
6. Projetar a mesma timeline para o ledger de cache com correspondência explícita
   entre cada conclusão de cópia/zero-fill e seu intervalo de escrita declarado.

Isso evita aceitar dois relatórios finais independentes que parecem bons, mas
descrevem endereços, tamanhos ou ordem incompatíveis. Não detecta fatos ocultos
fora da timeline nem transforma IDs em handles reais.

## Uma timeline, sem segunda lista de writes de payload

Input é tupla de eventos tipados de fase (`direct_staging_trace.Event`) e
publicação (`cache_publication_plan.Event`), em **ordem única**. No máximo 2.048
steps. Fase/ledger antigos permanecem inalterados e utilizáveis separadamente.

Para `copy-complete`/`zero-complete`, a composição produz somente **metadados**
de `write-claimed`, usando ID do recurso vinculado e
`required_offset + phase.offset`, com o tamanho da conclusão. Não copia bytes.
A origem de cada intervalo fica em `derived_payload_write_links`, com ordinais
zero-based na timeline e na projeção de publicação.

Claims explícitas de write para payload são recusadas, evitando omissão,
duplicação ou substituição por uma segunda lista. Só código/PGD/PUD admitem
`write-claimed` explícito, e somente depois de prepare e antes de seal.
No seal, todos os bytes requeridos dos **seis recursos** devem ter inicialização
declarada; não basta terminar os arquivos e deixar tabelas/código incompletos.

Não há bytes de código/tabelas, parsing de PTEs ou digest/readback dos destinos.
Claims de conteúdo do modelo de fases continuam alegações. Hashes de input
registram os arquivos de host, não o que uma CPU/DMA escreveria no alvo.

## Hipótese de ordem escolhida, não aprovação arquitetural

- Um único `observer-ack-claimed` depois de seal e antes das perdas/efeitos é
  exigido antes da fase abstrata `irreversible-boundary`.
- `observer-frozen` e `transport-lost` só aparecem após seal; sua ocorrência é
  opcional, nunca equivale a confirmação de efeitos ou futura recuperação.
- `no-inverse-attempt` só após a boundary e antes de `global-shutdown`, se usado.
  O shutdown global é um evento explícito, não inferido do nome da boundary.
- Claims PoC/I-cache somente após esse shutdown explícito e antes de final-clean.
- Em `final-clean`, gerar e verificar um `coverage-checkpoint` **nesse ponto**,
  cobrindo inicialização, D-cache e I-cache de código após a última escrita.
- Após seal não aceitar reescrita explícita de código/tabelas. A permissividade
  aritmética do ledger isolado não reabre a política de fases.
- `entry-described` termina apenas uma descrição consistente; qualquer evento
  posterior é recusado. Não chama entry nem emite permissão de execução.

A ordem é deliberadamente restrita para uma hipótese host. Não prova viabilidade
de helpers/mappings após shutdown, não escolhe instruções/barreiras e não aprova
o ponto real de irreversibilidade. As lacunas de exports/CFI/cache e múltiplas
fronteiras do fluxo legado continuam as da
[revisão anterior](2026-11-18-cache-publication-boundary-review.md).

## Falhas e limite de confiança

Falha/incerteza na timeline é declarada pelo evento de fase e propagada para o
ledger, sem canal independente de recuperação. EOF precoce também termina como
falha. Depois disso, nenhum evento de qualquer tipo é aceito, inclusive novas
claims de publicação, reads ou cleanup. Não há retry, release, fallback ou resume.

Os estados de erro de cada projeção conservam seu próprio limite abstrato:
boundary de fase e fences de efeitos não são automaticamente o mesmo evento.
Não inferir rollback da classificação de uma das projeções. O resultado ligado
nunca é completo se a fase termina em erro/incerteza, mesmo que a cobertura
numérica anterior continue completa no ledger.

`fixture_bindings_match` significa apenas vínculo consistente de metadados;
`full_fixture_description` exige descrição de entrada completa e cobertura
completa sem ledger terminal. Mesmo com ambos true, **runtime_admission_enabled,
ownership, autorização, readback/cache verificados, helper/writer implementados,
execução, cleanup, retomada e boot_ready permanecem falsos**. Replay de clones
coerentes pode coincidir; isso não prova estado atual, lifetime ou história real.

## Testes e tamanho dos cenários

Novo grupo `test-staging-binding-review.py` cobre fixture com text_offset
0/0x80000, cópias/zeros, leitura positiva curta, todos os prefixos, contexto misto,
IDs/bases/tamanhos/offsets divergentes, recursos auxiliares fora de RAM ou sobre
reserva estática, chosen não preparado, code write tardio, publicação antecipada,
ACK tardio/faltante, cobertura faltante e eventos após falha/incerteza.

Há também um cenário com **Image trim3 e initrd reais**, mas DT padded, RAM,
recursos e eventos inteiramente sintéticos, com buffer **declarado de 64 KiB**.
Ele cabe no limite de 2.048 steps e mantém a solicitação Image de 32 MiB.
Não é streaming implementado ou ensaio no alvo. Tentar validar seus pedidos de
64 KiB declarando buffer de 4 KiB é recusado.

Um traço completo trim3 com chunks de 4 KiB ultrapassaria o limite desta
composição e **não foi validado por ela**. Os modelos anteriores e a comparação
de memória com buffer de 4 KiB continuam resultados separados. Não apresentar
o teste de 64 KiB como validação do orçamento de 4 KiB ou economia medida.

Evidências em `private-diagnostics/staging-binding-host-01/`: fontes/logs/testes,
timeline pequena, cenário maior/DT sintético, projeções e hashes. Loader,
assembly, fontes dos três modelos anteriores, candidatos e arquivos de evidência
anteriores preservados; nenhum novo build ou comando no Quest.

## Próximo gate

Consistência host não fecha os gates reais de lifetime, isolamento, helper
PoC/CFI, entrada, CPUs/DMA/SMMU, QMP/watchdog ou logs/âncora. Antes de propor
qualquer port operacional, revisar quais evidências e contratos reais poderiam
substituir cada claim, começando por lifetime e ABI/CFI do eventual helper local.
Nenhuma autorização de aquisição, transferência, inserção ou execução decorre
deste modelo. Controlador e monitor operacional continuam bloqueados.
