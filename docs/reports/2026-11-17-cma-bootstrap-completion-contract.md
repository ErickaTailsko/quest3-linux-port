# Bootstrap — conclusão de transporte e âncora de reinício (rascunho host)

**Contrato puro implementado; 55 grupos host aprovados, zero falhas/ignorados.**
Esta etapa não implementa transporte live, armazenamento de âncora externa,
reconciliação operacional ou retomada. Nenhum comando no Quest foi executado;
controlador, journal anterior, fontes C e ELFs existentes foram preservados.

## Achado da revisão

O ACK de fixtures aceita a literal `host-fixture-complete`, que não pode ser
promovida a prova de completion real. O parser de framing existente, por outro
lado, valida nonce/status nos bytes, mas não sabe se o processo local foi
reaped, se as capturas terminaram, se houve timeout/interrupção, ou se o peer/
boot ainda é o esperado. São obrigações distintas.

`bootstrap_completion_draft.py` combina essas obrigações em envelopes canônicos
de um perfil separado `q3-bootstrap-completion-host-draft-v1`, sempre com
`producer=host-contract-model` e execução desabilitada. Não há I/O, criação de
arquivos, comandos, dispatcher, callbacks de transporte ou migração de journals.
O parser usado é o `transport_protocol.parse` existente, sem modificá-lo ou
chamar seu renderer de shell.

## Dados modelados

**Pending:** requisição completa e compromisso, papel fixo
`bootstrap-metadata-only`, token de transporte distinto de attempt/operação,
hash do intent do journal local e pins de pai/raiz/lease locais. Este hash de
journal é distinto do `local_intent_sha256` contido na requisição: o segundo
vincula o plano original; o primeiro identifica o registro local que o caller
deverá ter publicado antes do dispatch. O modelo não publica nenhum deles.

**Completion:** referência ao pending, recibo canônico/contextual, pins
candidatos, resposta/wire exatos e stderr bounded/base64 com tamanho/hash.
Para construir esse envelope, exige simultaneamente:

- observação local fornecida com exit zero, foreground reaped, streams completos
  e ausência de interrupção, usando campos/tipos exatos;
- dois samples fornecidos de boot iguais ao contexto esperado;
- exatamente um frame final `ERIS_CMA_DONE <token> <status>` com nonce original
  e status remoto zero;
- payload anterior ao frame exatamente igual à resposta do bootstrap esperada,
  vinculando operação e SHA-256 do recibo;
- recibo canônico correspondente à requisição, sem flags de ativação.

Um processo local que sai zero não prova sucesso remoto; um frame remoto zero
não corrige timeout/interrupção, stream incompleto ou wait local ausente.
Statuses remotos 125/126, outro erro, framing truncado/duplicado/estrangeiro,
boot divergente e resposta perdida não geram completion aceitável no modelo.

**Importante:** wait, boot e estado do transporte são observações **fornecidas**.
A biblioteca não autentica sua origem, nem comprova árvore de processos ou
quiescência. Conferir a estrutura dos bytes não estabelece história física.

## Checkpoint e comparação após reinício

O checkpoint proposto vincula pending/completion, hash opaco do ACK local,
recibo e pins. Os domínios SHA-256 de PENDING, COMPLETION e CHECKPOINT são
separados. Sua criação apenas calcula bytes; não grava, faz fsync, confirma
autorização ou transforma o hash do ACK em prova de seu conteúdo/publicação.
O publisher futuro ainda terá de garantir esse vínculo com o ACK real.

`review_restart` exige o compromisso de checkpoint que o caller já detenha por
uma âncora **independente da cauda examinada**, além de hash do ACK, pins locais/
peer e sample de boot fornecidos. Compara links e contexto; não acessa o peer
ou journal e não devolve um checkpoint de writer.

Mesmo o resultado `anchored-bytes-consistent-no-resume` mantém falsos:
proveniência/durabilidade da âncora externa, história de completion, recuperação
de writer, ACK local verificado, bootstrap/autorização, importação real, execução,
admissão, replay, cleanup, safe_to_mutate e retomada automática.

O teste de reescrita é explícito: alterar a captura e recalcular todos os hashes
é rejeitado pela âncora independente antiga. Se o caller escolher o novo digest
da própria cauda adulterada como âncora, a estrutura volta a coincidir, **sem**
comprovar proveniência ou história. A biblioteca não consegue distinguir essa
escolha indevida de uma âncora legítima: confiança externa é um pré-requisito,
não algo criado por hashes públicos.

## Ordem exigida para um futuro protocolo, ainda não implementado

1. Publicar e confirmar intent/pending local antes de qualquer dispatch.
2. Dispatch único com nonce/contexto previamente comprometidos, por adapter
   restrito e especificamente autorizado.
3. Validar wait/capturas/framing/recibo/contexto de origem confiável.
4. Publicar ACK local sem substituição e confirmar sua durabilidade.
5. Confirmar o checkpoint em mecanismo externo previamente confiável.
6. Considerar importação explícita separada; ativação/admissão continuam gates
   adicionais, não consequência automática da importação.

| Ponto de interrupção/incerteza | Limite preservado |
|---|---|
| Pending existe, dispatch/completion desconhecido | Não repetir; existência não prova se houve execução |
| Resposta perdida ou frame inválido | Congelar comandos, inclusive reads/cleanup automáticos |
| ACK visível, fsync/retorno não confirmado | Não gerar checkpoint confiável a partir do próprio arquivo |
| Commit da âncora externa incerto | Não inferir confirmação por ler outro arquivo autodeclarado |
| Âncora anterior conhecida, bytes/pins divergem | Rejeitar comparação; preservar evidência |
| Âncora coincide com bytes/pins fornecidos | Consistência somente; nenhuma retomada ou ativação |

Mover o mesmo problema para um segundo arquivo não fornece independência nem
resolve o último ACK incerto. A escolha de um mecanismo externo e de seu modelo
de falhas/rollback continua pendente; esta etapa não a presume resolvida.

## Testes e preservação

`test-bootstrap-completion.py` é um teste de bytes sintéticos: framing original,
tipos/limites, nonce/status, wait/capturas/boot fornecidos, campos adulterados,
contexto estrangeiro, checkpoints ausentes/divergentes e cauda reescrita.
Três compromissos conhecidos fixam a serialização/domínios para regressão:

- Pending: `d387e9e56d4f7e8d6d223d1cba3c0b35faaa198d2df63cf65a7d9ebbe6fe2a93`
- Completion: `086aee679f50280b8c1fa4dc663e6abc607561137ee72b41e82423cc0ced5ee6`
- Checkpoint: `24542385e271138006bb2eaa9763446929908d85ff3cc7bc2f79b3cc84f0013d`

São dados inteiramente sintéticos, não um plano autorizado para o Quest.
Snapshots, vetores de evidência e suíte/hashes são preservados em
`private-diagnostics/cma-bootstrap-completion-contract-01/`.

O journal host anterior continua aceitando somente suas fixtures originais;
nenhuma integração/admissão foi acrescentada. Os dois pares de ELFs Android
anteriores, módulo de identidade e Image trim3 permanecem preservados. Não houve
rebuild Android: esta etapa é Python e não altera CFI/SCS/LTO do kernel/módulo.

Próximo gate: escolher/revisar origem confiável das observações e mecanismo
independente de âncora, antes de implementar publisher/reconciliação operacional.
Transporte, ativação e qualquer operação no dispositivo continuam desabilitados
e dependem de revisão e nova autorização específica.
