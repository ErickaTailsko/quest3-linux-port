# Witness — log Merkle e monitor independente, modelo bounded de host

**Direção escolhida pelo usuário: log e monitor independente, começando offline.**
Foi implementado um modelo de bytes/assinaturas, com **59 grupos host aprovados**,
zero falhas e zero ignorados. Não há serviço, rede, armazenamento operacional
de log/monitor, integração com o controlador ou operação no Quest nesta etapa.

## Papéis e formato

`native-supervisor/witness_log_monitor.py` distingue três chaves públicas prévias:
witness, log e monitor. Reutilizar a mesma chave em dois papéis é rejeitado.
Nos testes as chaves estão no mesmo processo: isso **não comprova independência
de deployment**. O monitor real deverá estar fora do domínio capaz de reescrever
log/witness e conservar sua âncora de forma confiável.

O perfil é `q3-witness-log-monitor-host-v1`, produtor
`host-log-monitor-model`, sempre com execução desabilitada. A API não faz I/O,
buscas, persistência, emissão de comandos ou retomada. Os testes criam somente
fixtures locais para produzir declarações assinadas do witness anterior.

São modelados:

- **Entry:** requisição e declaração original do witness, preservando se foi
  `publication-confirmed` ou `record-observed`. Assinatura, chave e formato são
  conferidos. Isso não valida bootstrap, política do cliente ou documentos por
  trás dos digests; o wrapper de cliente anterior não foi integrado ao log.
- **Log head:** tamanho e raiz Merkle assinados pela chave do log, vinculados ao
  config de três papéis fixados.
- **Monitor checkpoint:** log head assinado, compromisso da varredura de bindings
  e hash do checkpoint anterior, assinados pela chave distinta do monitor.

A árvore usa a forma de domínio separado de RFC6962: SHA-256 de vazio para zero
folhas, `H(0x00 || leaf)` e `H(0x01 || left || right)`, com split pela maior
potência de dois estritamente menor que o tamanho. **Não é implementação do
protocolo wire de Certificate Transparency**, nem oferece provas compactas de
inclusão/consistência, gossip ou API de log.

## Verificação de extensão, sem descobrir uma âncora nova

O caller fornece o checkpoint anterior, seu compromisso **já detido**, o novo
log head e o prefixo completo. A referência limita a 128 entries, cada uma com
menos de 16 KiB, em vez de implementar fetch incremental ou provas compactas.

Para assinar uma extensão, o monitor-modelo exige:

1. Assinaturas/config válidos no checkpoint anterior e nos log heads.
2. Compromisso anterior coincidente com o valor fornecido pelo caller.
3. Crescimento estrito e número exato de entries; prefixo ausente não é buscado.
4. Raiz e varredura do prefixo antigo iguais às previamente comprometidas.
5. Raiz do prefixo completo igual à nova raiz assinada pelo log.
6. Todas as declarações do witness verificadas sob a chave anterior.
7. Nenhum pending associado a bindings checkpoint/contexto conflitantes dentro
   do prefixo apresentado.

Merkle append-only **não substitui a última checagem**: o log pode acrescentar
uma declaração conflitante sem reescrever folhas antigas. Essa extensão tem
raiz estrutural válida, mas o monitor recusa endossá-la por conflito semântico.
Várias declarações para o mesmo binding podem ser preservadas; não são votos
independentes e não há política de quorum nesta direção escolhida.

As funções apenas devolvem bytes de fixtures. Não gravam automaticamente o novo
checkpoint, não escolhem o “mais recente” de uma cauda observada e não atualizam
o journal/controlador existente.

## Limite central: estado mais recente do monitor

O teste fornece genesis antigo ao mesmo signer de monitor e constrói uma segunda
história válida. Ambas podem ter assinaturas corretas. A âncora atual correta
recusa aquela mudança de branch, mas **o modelo não sabe se o caller forneceu
deliberadamente um checkpoint antigo**.

Portanto, log + chave distinta + hashes não resolvem sozinhos rollback do estado
do monitor. Sua âncora atual precisa de origem, persistência e proteção contra
rollback independentes, com política de falhas explicitamente revisada. Criar
outro arquivo no mesmo domínio ou chamar um digest de “último” não estabelece
esse requisito. Nenhum armazenamento desse tipo foi provisionado nesta etapa.

O caso de fork oculto também permanece: uma extensão coerente apresentada ao
monitor não demonstra que outro log/monitor não assinou uma história escondida.
Gossip/observação independente, confiança e política contra equivocalidade
continuam sendo obrigações de deployment, não fatos assumidos pelo teste.

## Assinatura versus rechecagem completa

`review_checkpoint` confere assinaturas e compromisso fornecido, mas não recebe
as entries. Seu resultado declara `full_prefix_rechecked_here=false`. O teste
inclui checkpoint assinado com digest de varredura incorreto: inspeção de bytes
assinados não o detecta sozinha, enquanto a tentativa de extensão com prefixo
completo o rejeita. Não se deve promover inspeção de assinatura a reexecução da
política do monitor.

Mesmo resultados positivos mantêm falsos origem/frescor da âncora, independência
real, append-only operacional, rollback/não-equivocação, exclusão de forks
ocultos, entrega original, ACK/bootstrap/autorização, pin import, execução,
admissão, replay, cleanup, recuperação de writer e retomada automática.

## Testes e preservação

`test-witness-log-monitor.py` cobre árvore vazia/1/2/3 folhas com hashes esperados,
chaves/domínios distintos, genesis, extensões, repetição do mesmo binding,
redução/reordenação/reescrita, prefixo faltante, raiz divergente, conflito anexado,
witness estrangeiro, headers/checkpoints assinados mas inválidos, adulteração de
assinatura e limites de dados. Também demonstra baseline antigo, história oculta
e diferença entre inspeção assinada e rechecagem completa.

Fontes, log de testes, vetores públicos de prefixos/heads/checkpoints sem chave
privada, suíte e hashes são preservados em
`private-diagnostics/cma-witness-log-monitor-host-01/`. Fontes anteriores, dois
pares de ELFs Android, módulo de identidade e Image trim3 foram reconferidos.
Nenhum pacote foi instalado e nenhum rebuild Android foi necessário.

Próximo gate: especificar armazenamento/recuperação da âncora mais recente do
monitor e a fronteira independente de confiança antes de implementação ou
deployment operacional. Nenhum resultado deste modelo libera comandos no Quest.
