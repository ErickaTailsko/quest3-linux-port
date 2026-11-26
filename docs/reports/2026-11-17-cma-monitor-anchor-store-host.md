# Monitor — store host com intenção durável antes da assinatura

**Referência de armazenamento implementada apenas para fixtures de host.** A
suíte completa aprovou **60 grupos**, zero falhas e zero ignorados; o teste
específico também passou sob o filesystem do projeto. Não houve deployment,
rede, chave operacional, integração com controlador ou operação no Quest.

## Mudança de ordem: validar, reclamar, assinar, publicar

`native-supervisor/monitor_anchor_store.py` usa um writer single-threaded por
vida de processo. A sequência suportada é:

1. Conferir head atual, âncora fornecida, assinaturas e prefixo completo pelo
   contrato de log/monitor existente.
2. Produzir o payload **ainda sem assinatura** do próximo checkpoint.
3. Inserir intenção com predecessor único em SQLite, COMMIT com synchronous=FULL
   e fsync do diretório; reconferir head e intenção.
4. Somente depois chamar o assinador do monitor.
5. Publicar checkpoint e novo head na mesma transação, com compare-and-swap do
   head anterior e preenchimento exclusivo da intenção ainda pendente.
6. Confirmar COMMIT/fsync, reconferir registros e devolver os bytes assinados.

`witness_log_monitor.py` foi refatorado para expor `prepare_monitor_extension`,
separando validação de assinatura. A API stateless anterior permanece compatível;
ela **não** ganha automaticamente a barreira do store. O fonte anterior foi
preservado no arquivo de evidências, e uma comparação com o signer anterior
confere que os mesmos inputs/chave continuam produzindo os mesmos bytes.

Esses helpers raw e as chaves de fixtures não são uma fronteira de segurança
contra quem controla o processo. Um serviço real teria de impedir bypass do
store/assinador e isolar chave/estado/política do cliente. Isso não foi instalado.

## Raiz, lease e banco

O caller fornece pai privado e pins anteriores. A referência cria a raiz fixa
`q3-monitor-anchor` exclusivamente: qualquer objeto existente, inclusive estado
parcial, bloqueia novo create. São fixadas identidades de pai, raiz, lease e
`anchor.sqlite3`, com owner/modos 0700/0600 e nlinks de arquivos conferidos.
A enumeração bounded abre um FD novo de `.` a cada checagem.

SQLite usa journal DELETE, FULL sync e transações explícitas. A identidade do
store compromete config de chaves e genesis previamente assinado/ancorado. Head,
intenção e histórico são reconferidos; o writer mantém também cópia esperada
dos registros de sua vida atual para detectar adulteração observável. Quantidade
e tamanho de registros são limitados antes de carregar os blobs do histórico.

O predecessor é chave única: uma intenção consumida não é reutilizada pelo
writer. A atualização de head só aceita os bytes anteriores exatos. Assinatura
não é devolvida antes da publicação final. Isso testa ordem de chamadas e
persistência sob as premissas do host, **não** power-loss real ou resistência
a snapshots/atores privilegiados.

## Falhas e disponibilidade deliberadamente limitada

Qualquer erro congela o handle, incluindo validação, publicação, fsync incerto
ou perda do retorno. Não há retry, reset, takeover, busca automática ou reabertura
de writer. `close` apenas fecha recursos; SQLite pode desfazer sua transação
local não confirmada, sem remover a raiz/barreira de criação.

| Interrupção | Evidência possível, sem permissão de retomada |
|---|---|
| Antes do COMMIT da intenção | Banco pode conter só genesis; raiz continua barreira |
| Depois da intenção, antes de publicar checkpoint | Intenção pendente; sua presença não prova se a assinatura chegou a ocorrer |
| Depois da assinatura, antes do COMMIT do checkpoint | Intenção ainda pendente; checkpoint não é recuperado de memória nem repetido |
| Depois do COMMIT/fsync, antes de retorno conhecido | Checkpoint/head podem estar completos, mas a entrega/confirmação original continua desconhecida |

Os testes contam chamadas reais ao assinador para confirmar zero assinaturas
nas falhas anteriores à barreira durável. A inspeção de disco **não** usa essa
contagem do teste como prova histórica de que nunca houve assinatura.

## Reabertura somente observacional

`open_observer` exige pins anteriores do store, chaves públicas e genesis
ancorado. Usa lease não bloqueante, conexão read-only/query_only e não recebe
chave privada. Journal residual/arquivos extras são rejeitados antes da conexão,
sem recuperação automática de hot journal.

A inspeção percorre a cadeia bounded de intenções/checkpoints, confere
assinaturas, predecessor, payload exato da intenção, crescimento e head final.
Exige que o digest mais recente detido pelo caller esteja nessa cadeia.
Não recebe entries de log: declara `full_prefix_rechecked_here=false`, sem
reexecutar a varredura semântica de bindings nessa inspeção.

Os estados diferenciam âncora coincidente, intenção retida e descendente visível
ainda não ancorado pelo caller. O digest observado é só metadado forense; não é
novo checkpoint confiável nem autorização de importação. Entrega original,
durabilidade de produção, recuperação de writer e retomada permanecem falsos.
Mesmo fechamento limpo não oferece reabertura para escrita nesta referência.

## Limite de rollback preservado

Um teste restaura os bytes de um snapshot antigo no **mesmo inode** do banco.
A âncora externa mais recente detecta que seu checkpoint sumiu. Se o caller
também fornecer uma âncora antiga coerente, a inspeção pode coincidir novamente;
as flags de frescor, independência e proteção contra rollback continuam falsas.

Portanto, SQLite + pins + intenções não substituem armazenamento/autoridade
independente da âncora atual. Clonar/reinicializar outro domínio com as mesmas
chaves também está fora da garantia. O store não resolve sozinho revogação,
estado monotônico, forks ocultos, recuperação operacional ou isolamento real.

## Testes e preservação

`test-monitor-anchor-store.py` cobre ordem fsync/assinatura, compatibilidade de
bytes com o signer stateless, predecessor único, CAS, âncora/prefixo inválidos,
conflito anexado, corrupção de intenção/head/config, perda de retorno, todos os
estágios de COMMIT/fsync, fsync concluído mas retorno incerto, read-only após
reinício, snapshot antigo e SIGKILL antes de assinar/depois de publicar.

Executa em diretórios temporários de host. O teste adicional usa
`Q3_MONITOR_TEST_TMP="$PWD/private-diagnostics"`. Fontes (incluindo versão anterior
do modelo), logs nos dois filesystems, vetores públicos, suíte e hashes estão em
`private-diagnostics/cma-monitor-anchor-store-host-01/`. Chaves privadas de
fixtures não são serializadas. Nenhum pacote ou binário Android foi instalado,
baixado, executado ou reconstruído nesta etapa.

Próximo gate: definir a autoridade/armazenamento independente da âncora mais
recente e política de recuperação operacional, mantendo a fronteira que impede
assinatura fora do store. Nenhum resultado habilita comandos no Quest.
