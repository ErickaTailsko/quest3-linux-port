# Witness separado — referência SQLite/Ed25519 apenas no host

**Direção escolhida pelo usuário: witness separado, começando por testes locais,
sem instalar serviços.** Foi implementada uma referência sem rede ou daemon;
a suíte completa aprovou **56 grupos**, zero falhas e zero ignorados.

Não houve configuração de contas, serviço, firewall, chave operacional ou máquina
externa. Nenhuma operação no Quest, transporte live, integração com o controlador,
rebuild Android, inserção de módulo ou alocação foi realizada.

## Domínio de confiança pretendido, ainda não provisionado

O witness de produção deverá ter identidade, chave privada, política de escrita
e armazenamento fora do domínio que pode reescrever a cauda do journal examinado.
Outro diretório sob o mesmo UID não fornece essa separação. Os testes executam
no mesmo host/processo de fixture: **não demonstram isolamento real**.

A chave pública do witness deverá ser fixada antes da tentativa por canal
independente revisado. Não pode ser aprendida da própria resposta. A chave
privada não deve ser entregue ao controlador ou ao dispositivo. Autenticação do
cliente, autorização de publicação, provisionamento/rotação e transporte entre
domínios continuam pendentes; a referência não pressupõe que uma assinatura
substitua esses controles.

## API restrita de referência

`native-supervisor/bootstrap_witness_reference.py` aceita somente requisições
canônicas bounded com hashes de pending/checkpoint/contexto e nonce. Não recebe
comandos, paths remotos, ELFs, PFNs, pools, opções de módulo ou ações de handoff.
Seu perfil é `q3-bootstrap-witness-host-reference-v1`.

O witness **notariza um vínculo de digests**. Ele não valida os documentos por
trás desses hashes, nem atesta autorização, bootstrap, identidade real, completion
ou aquisição de memória. Vínculos falsos fornecidos por um cliente não se tornam
fatos verdadeiros por terem sido assinados.

Cada compromisso de pending admite um único par checkpoint/contexto na mesma
base. Nova publicação do mesmo vínculo é idempotente; vínculo conflitante é
recusado e congela o handle. Isso é repetição de notarização, **não** replay de
comando no Quest e não garantia global de exatamente-uma-vez. O limite de fixture
é 128 vínculos. Quotas/política de namespaces de produção ainda não existem.

## Armazenamento e ciclo de vida das fixtures

A criação exige pai privado previamente fixado e usa raiz fixa exclusiva
`q3-bootstrap-witness`. Qualquer raiz existente, inclusive parcial, impede nova
criação. São fixados dev/inode de pai, raiz, lease e banco; tipos, owner, modos
0700/0600 e nlinks dos arquivos são conferidos. A lease é exclusiva/não bloqueante.

SQLite é aberto por caminho relativo ao FD da raiz em `/proc/self/fd`, com
`journal_mode=DELETE`, `synchronous=FULL`, transação explícita e fsync do diretório
antes de assinar a confirmação. A identidade da chave é registrada no banco;
troca de chave sem revisão é recusada. O binding é reconferido antes de assinar
e antes de devolver a declaração.

Essas são barreiras de referência no host, não validação de durabilidade em
power-loss, hardware, filesystem remoto ou rollback de snapshots. SQLite não
torna o arquivo imutável contra quem administra o armazenamento. A API não
atualiza/remove bindings, mas um ator privilegiado pode alterar a base.

Qualquer erro congela o handle; chamadas seguintes falham antes de consultar ou
assinar. `close` fecha FDs/conexão; SQLite pode desfazer sua própria transação
local não confirmada. Essa manutenção do banco não é cleanup de dispositivo e
não remove a raiz nem permite novo create. Não há reopen de writer.

Após fechamento/morte, só existe abertura explícita de observador com pins
anteriores, chave correspondente, SQLite read-only e query_only. Estado com
journal residual ou arquivo extra é recusado antes da conexão: não se executa
recuperação automática de hot journal. Esse modelo conservador pode perder
disponibilidade e exige revisão separada em caso de crash parcial.

## Duas declarações assinadas, sem confusão de semântica

As declarações Ed25519 vinculam requisição/nonce exatos, fingerprint da chave,
binding e hashes contextuais com domínio separado:

| observation | O que a referência fez |
|---|---|
| publication-confirmed | COMMIT retornou, fsync do diretório retornou e o vínculo foi reconferido antes de assinar |
| record-observed | Uma consulta explícita encontrou agora o vínculo no witness |

Uma consulta posterior não recria a resposta original de publicação nem prova
que o caller a recebeu. O verificador exige a observation esperada; uma resposta
`record-observed` não satisfaz uma exigência de `publication-confirmed`.
Nonce estrangeiro, alteração de payload, assinatura inválida, chave não fixada,
tipos divergentes e campos extras são rejeitados.

Repetir a mesma requisição gera a mesma assinatura determinística. Não há relógio,
contador monotônico ou prova de frescor na assinatura: o caller futuro deverá
comprometer um nonce novo antes de uma consulta e validar o contexto. A referência
não conecta essas consultas ao controlador congelado ou as dispara automaticamente.

O resultado positivo informa `signature_verified=true` somente para bytes que
verificam sob a chave fornecida previamente. Independência do deployment,
proteção contra rollback, não-equivocação, entrega original, durabilidade de
produção, história de execução, ACK local, importação/admissão, retomada, cleanup
e recuperação de writer continuam explicitamente **falsos**.

## Limite demonstrado: rollback e equivocalidade

Um teste cria duas bases de fixtures com a mesma chave e publica, em cada uma,
um checkpoint diferente para o mesmo pending. Ambas as assinaturas são válidas
para suas requisições. A política de vínculo único vale em cada base, mas uma
assinatura isolada não detecta clonagem, rollback ou duas histórias do witness.

Portanto, **SQLite + Ed25519 não resolve sozinho a âncora independente**. Um
deployment real precisa de política confiável contra rollback/equivocação, além
de isolamento e autenticação. Exemplos a revisar: log independente com comparação
de checkpoints, armazenamento monotônico confiável ou testemunhas independentes
com política de quorum. Nenhum deles foi configurado ou escolhido implicitamente.

## Testes e evidência

`test-bootstrap-witness.py` usa SQLite real e Ed25519 da biblioteca Python
`cryptography` já presente no host; nenhum pacote foi instalado/baixado.
Chaves privadas são geradas em memória para fixtures e descartadas. Não são
chaves operacionais nem entram no manifesto/arquivo de evidências.

Na primeira tentativa de arquivar uma fixture no filesystem do projeto, o
catálogo pelo FD aberto antes da criação dos arquivos retornou vazio, apesar de
lease/banco serem acessíveis por nome. A referência falhou fechada antes de abrir
SQLite/assinar. As duas tentativas incompletas foram preservadas, sem retry sobre
a mesma raiz. O leitor passou a abrir um novo FD de `.` para cada catálogo.
Após a correção, os testes passaram tanto em `/tmp/opencode` quanto em diretório
temporário sob `private-diagnostics`; a suíte completa foi repetida com sucesso.
Isso não constitui garantia contra todas as corridas/cache de filesystems.

Para repetir o teste adicional no filesystem do projeto, sem tocar nas raízes
arquivadas:

```sh
Q3_WITNESS_TEST_TMP="$PWD/private-diagnostics" \
  python3 quest3/cma-identity-query/native-supervisor/test-bootstrap-witness.py
```

Os testes cobrem publicação, idempotência, conflito, capacidade bounded, tipos/
assinaturas/nonces, chave estrangeira, resposta de observação usada indevidamente
como confirmação, falhas nos estágios de commit/fsync/assinatura/retorno,
substituições de objetos, adulteração antes de responder, reabertura somente
observacional e SIGKILL após COMMIT antes da resposta. O teste de duas histórias
documenta o limite de rollback/não-equivocação, sem alegação de proteção.

Fontes, logs, versão das dependências, vetores públicos assinados (sem chave
privada), fixture de banco e suíte/hashes são preservados em
`private-diagnostics/cma-bootstrap-witness-host-01/`. Fontes anteriores e dois
pares de ELFs Android, módulo de identidade e Image trim3 foram reconferidos.

## Próximo gate

Revisar proteção contra rollback/equivocação, identidade do cliente e política
do witness antes de projetar seu deployment separado ou qualquer integração.
Não substituir a âncora externa do contrato anterior por um digest aprendido
da mesma resposta. Nenhuma declaração desta referência habilita pin import,
writer nativo, transporte ADB/su ou ação no Quest.
