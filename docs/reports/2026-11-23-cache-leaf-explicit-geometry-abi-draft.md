# Geometria explícita — proposta documental de ABI, draft v2

**DRAFT, não adotado nem implementado.** Identificador:
`q3-cache-leaf-explicit-geometry-abi-draft-v2`.
Não substitui `q3-cache-leaf-acceptance-contract-host-v1`; não cria símbolo,
header, candidato ou modo novo de verificação. B0 permanece PENDING.
Continua a [revisão hotplug/ABI](2026-11-23-cache-leaf-b0-hotplug-abi-review.md).

## 1. Decisão proposta

Estudar um leaf local de chamada direta, retorno void, com três argumentos
LP64: VA inicial (`void *`), comprimento em bytes (`size_t`) e passo em bytes
(`size_t`). O terceiro argumento ocuparia x2 pela ABI AArch64; isso é uma
especificação, não declaração C adicionada ao projeto.

O leaf não consulta CTR nem símbolos públicos/privados, não chama outra função
e não lê global de geometria. O caller seria responsável por obter e validar a
geometria antes da chamada. Não selecionar agora instruções de manutenção,
barreiras ou estratégia concreta de hotplug.

Continuam as restrições de x0–x3/NZCV, x18/SCS, callee-saved, SP, BTI e retorno
PAC do contrato anterior. x2 deixa de ser apenas scratch inicial e passa a ter
semântica de input. Viabilidade dentro desse conjunto de registradores exige
revisão futura do corpo inteiro; não ampliar registradores implicitamente.
Não admitir argumento escondido, callback, ponteiro em dados ou ABI híbrida v1/v2.

## 2. Passo de cobertura e envelope de efeitos são obrigações distintas

**S**: passo seguro para atingir todas as linhas relevantes, derivado de
geometria demonstrada para o domínio de CPUs permitido. DminLine sanitizado é
uma fonte candidata, não prova completa de contexto ou erratas.

**G**: limite de granularidade/alinhamento dos efeitos das operações realmente
escolhidas em todas as CPUs/contextos permitidos. É necessário demonstrar que
o envelope arredondado por G contém esses efeitos. Não confundir G com S,
nem aceitar `cache_line_size()`/CWG como G sem prova arquitetural e de plataforma.

Um passo mínimo pode evitar saltar linhas e ainda assim não limitar os bytes
afetados por uma linha maior. Exemplo exclusivamente sintético: S=64, linha
efetiva de 128, extensão declarada [64,128). Operar em VA 64 pode atingir a linha
[0,128), incluindo bytes fora da extensão. Não são endereços do Quest.

Assim, arredondar ownership apenas por S não basta para o caso heterogêneo.
Proposta conservadora: exigir S e G potências de dois, G >= S, G múltiplo de S,
com a relação comprovada e o envelope por G contido numa única extensão própria
viva. Se não houver limite G justificado, recusar operacionalmente e manter
a avaliação de plataforma PENDING. Um inteiro plausível não prova essa relação.

G fica como obrigação explícita do preflight do caller, não como quarto
argumento implícito. Isso não prova que o corpo do leaf respeita o envelope:
a sequência/endereço de cada operação ainda precisa ser revisada.

## 3. Preflight proposto — sem código executável

Antes da primeira manutenção, o caller deve demonstrar:

1. VA, comprimento, S e G sem narrowing, signedness ambígua ou unidade errada.
2. Geometria obtida por caminho público revisado, ID correto, tabela válida e
   valor suportado. Fallback zero do leitor não é uma geometria autenticada.
3. Domínio de CPUs e estabilidade de S/G durante todo o uso, com exclusão de
   mudanças incompatíveis demonstrada; dupla leitura e pin de migração não bastam.
4. Mapping normal kernel válido com MMU ativa e atributos revisados, recurso
   próprio/retido e domínio de efeitos conhecido. VA traduzível não prova posse.
5. Ausência de overflow de VA+len, extensão e arredondamento por S e G.
6. Envelope por G integralmente dentro de uma única extensão própria; não
   combinar objetos adjacentes. Inclusão deve valer também para efeitos por linha.
7. Última escrita, exclusão de writers/DMA, contexto de erratas e lifetime até
   conclusão. Ownership declarado não é evidência real desses fatos.

Comprimento zero: caller não chama leaf nem reivindica publicação. O leaf
também precisa de caminho zero sem manutenção e com retorno PAC correto.
Para input inválido não zero, o caminho autorizado é recusa no caller antes
de efeitos; retorno void não oferece canal de erro nem recuperação de abort.
O contrato não promete tolerância a chamada arbitrária inválida do leaf.

Os valores 16/32/64/128/256 do modelo host atual são hipóteses aritméticas,
não uma allowlist de hardware. Não adotar automaticamente todo encoding CTR,
nem tratar valores fora do perfil como aprovados por serem potência de dois.

## 4. Contextos explicitamente não aprovados

- Não manter lock de hotplug através de shutdown por esta proposta.
- Não inferir validade pós-shutdown de uma geometria obtida pré-shutdown.
- Não inferir que desabilitar preempção exclui CPU hotplug, DMA ou outros writers.
- Não usar o leaf como trampoline físico, manutenção com MMU desligada,
  entrada do segundo kernel, callback ou rotina copiada para outro endereço.
- Não interpretar retorno normal como prova de publicação física, I-cache,
  DMA quiet, logs persistidos ou viabilidade de handoff.

Nenhum mecanismo de estabilização foi escolhido/implementado. Esse é um
bloqueio real de plataforma, não um campo de metadata a preencher como PASS.

## 5. Mudanças de evidência necessárias antes de adotar

| Obrigação | Evidência futura necessária |
|---|---|
| ABI | Declaração única três-argumentos, tipos efetivos e caller/corpo com a mesma versão |
| L03/L04 | BL ao destino pretendido, sem escape/callback/tail-call não revisado |
| L05–L08 | CFI/SCS/Full LTO preservados, BTI, preservação e PAC em todos os retornos |
| L11 | S, G, domínio de CPUs, estabilidade, erratas e envelope efetivo demonstrados |
| L12/L14 | Operação/barreiras e ponto de chamada revisados separadamente de geometria |
| Verificador | Dispatch explícito por perfil, recusa de perfil desconhecido e fixtures de ABI misturada |
| Aritmética | Separar cobertura por S e containment dos efeitos por G, sem atribuir ownership real |

O verificador estático atual não demonstra a semântica do terceiro argumento
nem a relação S/G. `review_range()` só arredonda pela linha fornecida. Seus
PASS locais não podem ser reetiquetados como aprovação deste draft.
Não atualizar resultados históricos ou usar a rejeição PAC histórica como
evidência positiva de uma nova ABI. Os verificadores permanecem inalterados.

Controles futuros mínimos, ainda **não implementados**: caller v1 contra leaf
v2, geometria em unidade errada, S/G inválidos, G<S, overflow no envelope G,
extensão alinhada a S mas não contendo os efeitos G, mudança de domínio CPU,
retorno zero sem PAC, retenção perdida por LTO e metadados consistentes com
semântica de linha não demonstrada.

## 6. Disposição

Proposta escrita; não é adoção do perfil nem autorização de implementação.
Próximo gate offline: revisar o envelope de efeitos e as opções públicas de
estabilização num contexto pré-shutdown delimitado, sem segurar locks através
do shutdown; então decidir se o draft pode virar contrato revisado.

Init do eventual candidato permanece de recusa incondicional, sem alcançar
caller/helper, sem parâmetros/endpoints/allocators. Nenhum fonte candidato,
preprocessamento, build, loader ou operação no Quest nesta etapa.
Progresso ~40% subjetivo; B0 PENDING.
