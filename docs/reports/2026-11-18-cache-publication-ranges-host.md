# Publicação por intervalos e última escrita — ledger host

**66 grupos host aprovados, zero falhas/ignorados.** Novo modelo separado:
`quest3/layout-review/cache_publication_plan.py`. Não implementa helper, cache
maintenance, writer, I/O, mapping, entrada ou transporte. Eventos são alegações
de fixtures, não operações despachadas nem evidência física.

Continua a [revisão de cache/fronteiras](2026-11-18-cache-publication-boundary-review.md).
Loader, assembly, modelo de fases anterior e candidatos permanecem inalterados.

## Recursos e escopo geométrico

O input exige seis `Resource` imutáveis: Image, initrd, DT, código, PGD e PUD.
Cada recurso tem ID fictício, extensão física sintética, offset/tamanho do range
que precisa ser inicializado e provenance `host-fixture-only`. IDs não podem
coincidir entre si ou com boot/attempt; boot e attempt são distintos.

Os slots completos precisam ser page-aligned, bounded em PA48 e disjuntos,
incluindo padding. Limites: até 32 MiB Image, 2 MiB initrd/DT e uma página por
recurso de código/tabela. Os três recursos de transição continuam hipótese
geométrica, não orçamento suficiente comprovado ou páginas construídas.

Eventos usam offsets relativos ao recurso. Writes precisam estar **inteiramente
no range requerido**, não no prefixo text_offset nem no restante do slot.
Claims de cache podem abranger linhas completas dentro do slot, inclusive bytes
adjacentes ao tail no mesmo slot. Não podem ultrapassar a alocação ou cobrir
outro recurso por coincidência de endereço.

O ledger não faz parsing de Image/DT ou validação RAM/reservas/PTEs, não escolhe
bases e não adquire handles. Não substitui `returned_layout.py`. As fixtures
começam em 64 GiB, fora da RAM capturada do Quest; não propõem endereço real.

## Invariantes de cobertura

Ranges são half-open `[início, fim)`. Um algoritmo de união/subtração de
intervalos evita enumerar todas as linhas de uma Image grande. Para cada recurso:

- `write-claimed`: une bytes declarados inicializados; marca dirty todas as
  linhas D-cache tocadas, arredondando início para baixo e fim para cima; registra
  ordinal **zero-based** da última escrita no recurso.
- `poc-claimed`: exige início/fim alinhados à linha D-cache assumida e dentro
  do slot. Subtrai essas linhas do conjunto dirty atual. **Não inicializa bytes**.
- Uma escrita posterior recoloca as linhas afetadas no conjunto dirty. Um clean
  anterior nunca publica retroativamente uma escrita futura.
- `icache-claimed`: permitido só para código já inteiramente inicializado e sem
  linhas D-cache dirty declaradas; exige alinhamento à linha I-cache assumida.
  Os ranges I-cache precisam cobrir todo o código requerido para um checkpoint.
- Qualquer escrita de código invalida conservadoramente **toda** sua cobertura
  I-cache declarada, além de tornar dirty as linhas D-cache tocadas. Reclean
  dessas linhas não restaura sozinho a cobertura I-cache.
- `coverage-checkpoint`: exige todos os bytes requeridos inicializados, nenhuma
  linha D-cache dirty em qualquer recurso e cobertura I-cache completa do código.

Tamanhos D/I são parâmetros **assumidos** e independentes: 16/32/64/128/256 bytes.
Não há leitura de CTR, prova de linha segura entre CPUs ou aplicação de errata.
PoC/I-cache são nomes de claims, não certificação da instrução/barreira correta.
Writes não carregam bytes: digest, zero-fill real e readback não são verificados.

Um recurso nunca escrito pode ter conjunto dirty vazio. Portanto, ausência de
dirty **sozinha** não comprova publicação: o checkpoint também exige cobertura
completa dos bytes. O buffer de streaming não foi adicionado aos destinos de
entrada; esta lista não inventaria todos os recursos vivos do kernel antigo.

## Última escrita e relação com os outros modelos

Exemplo sintético: código de 400 bytes, D/I-cache de 64 bytes. Após inicializar
os 400 bytes, é necessário declarar PoC e I-cache cobrindo `[0,448)`. Uma escrita
posterior de um byte em offset 23 torna `[0,64)` dirty e invalida I-cache. Somente
republicar D-cache nessa linha e I-cache de todo o código recompõe as claims.
Isso modela a lacuna de clean anterior a uma eventual reescrita tardia de código.

Esse ledger **permite registrar** writes posteriores para calcular invalidação;
não os autoriza. `direct_staging_trace.py` continua separado e recusa mutações
após selagem. Não foi relaxada sua política. Os modelos não estão integrados:
um resultado numérico não pode reabrir staging, habilitar probe ou liberar entrada.

Checkpoints são snapshots de claims. O contador histórico de checkpoints não é
um selo permanente: depois de nova escrita, a cobertura atual volta a incompleta.
Reapresentar IDs/tuplas idênticos também não prova lifetime ou história física.

## Fronteiras e falhas independentes

Eventos distintos registram `observer-frozen`, `transport-lost`,
`no-inverse-attempt` e `global-shutdown`. Não se impõe uma ordem arquitetural
completa entre eles; são marcadores de fixture, não o sequenciador da plataforma.
Duplicatas são recusadas. `observer-ack-claimed` é recusado depois de qualquer
dessas fronteiras, conservadoramente sem presumir observador normal disponível.
Um ACK anterior não é autorização ou prova dos efeitos futuros.

Timeout, interrupção, journal falho, conclusão desconhecida ou restart terminam
em `FROZEN_UNKNOWN`. `known-failure` termina em `FAILED_RETAINED` antes de
`no-inverse-attempt`/`global-shutdown`, ou `FAILED_AFTER_IRREVERSIBLE` depois.
Todos recusam qualquer evento posterior, inclusive read, cleanup, resume e
novas claims. Não há API de liberação, retry, fallback ou execução.

Informação numérica anterior pode continuar completa em um resultado terminal;
isso **não** significa prontidão ou recuperação. Os campos de autorização,
ownership, cache verificado, helper implementado, execução, cleanup, retomada e
boot_ready continuam falsos em todos os resultados, inclusive checkpoints.

## Testes e evidências

Novo grupo `test-cache-publication-plan.py` cobre:

- Cobertura dos seis kinds, writes fragmentados/unaligned, tails e linhas comuns.
- Todas as 25 combinações assumidas de tamanho de linha D/I.
- Reescrita em cada recurso depois de checkpoint, invalidação parcial de D-cache,
  invalidação completa de I-cache do código e republicação declarativa.
- Clean antecipado, bytes não inicializados, linha final faltante, I-cache parcial,
  writes em prefixo/padding, ranges/tipos/contextos inválidos e slots aliased.
- Fronteiras independentes, ACK tardio e todos os motivos de falha/incerteza em
  cada prefixo do traço principal, com comandos posteriores rejeitados.
- Oráculo independente de sets de bytes/linhas para 300 eventos seeded de writes
  e cleans fragmentados, confrontado com o algoritmo de intervalos a cada passo.

Nenhum teste comprova operação real de cache, semântica de helper assembly, CFI,
barreiras, PA/PTEs, lifetime ou ausência de DMA. Não é model checking exaustivo.
Evidência em `private-diagnostics/cache-publication-ranges-host-01/`: fontes,
testes/logs, fixtures/resultados e hashes, preservando os arquivos anteriores.

## Próximo gate

Revisar o vínculo **somente host** entre layout, traços de fases e ledger de
cobertura: mesmo contexto/recursos/ranges e tratamento coerente da última escrita,
sem converter consistência de fixtures em admissão runtime. Ainda não existe
helper aprovado, writer ou transição sem cópia; nenhum destino foi adquirido.
Monitor/âncora, logs, CFI/SCS/Full LTO/MODVERSIONS, CPU/DMA/SMMU/QMP/watchdog e
autorização específica para qualquer operação no Quest continuam gates abertos.
