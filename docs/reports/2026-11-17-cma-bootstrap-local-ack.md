# ACK local e importação de pins — referência host, sem admissão

**Referência de filesystem implementada e testada apenas em fixtures do host.**
A suíte completa aprovou **54 grupos**, zero falhas e zero ignorados. Nenhuma
operação no Quest, transporte, rebuild de ELF Android, inserção de módulo ou
alocação foi feita nesta etapa. O controlador e os artefatos anteriores foram
preservados.

## Separação entre observar, confirmar e importar

`native-supervisor/bootstrap_ack_reference.py` não modifica o parser/observador
do bootstrap, o supervisor nativo, o contrato v3 ou o controlador. É uma biblioteca
Python separada, de writer single-threaded, sem CLI operacional, dispatcher ou
API de recuperação do writer. Chamadas concorrentes na mesma instância não são
uma interface suportada; a exclusão testada é entre criadores/observadores distintos.

Seu protocolo de fixtures distingue três registros locais:

1. **intent.json**: requisição de bootstrap esperada, seu compromisso e os pins
   previamente fixados do pai local e da nova raiz/lease do journal.
2. **ack.json**: vínculo ao intent, recibo canônico fornecido, resposta exata,
   pins candidatos e classificação explícita `host-fixture-complete`.
3. **import.json**: compromisso do intent/ACK e cópia explícita dos pins de
   fixture, sem ativação ou admissão.

O perfil é `q3-bootstrap-pin-ack-host-reference-v1`, produtor
`host-fixture-journal`. A raiz local tem nome fixo `q3-bootstrap-pin-ack`, sob
pai privado 0700 previamente fixado. `create` usa mkdir exclusivo e lease
0600/flock; qualquer estado existente, inclusive vazio/parcial, impede criação.
Não há takeover, TTL, reset, reopen para escrita ou retry após falha.

O caller recebe o writer somente após publicação do intent. A operação de ACK
exige requisição/recibo/contexto canônicos, resposta exata e pins de fixture
fornecidos separadamente que coincidam com o recibo. A literal de completion é
**somente uma fixture fornecida pelo caller**, não um validador de framing,
wait/reap, exit status ou autenticidade de transporte real. O código não consulta
um dispositivo nem chama observadores remotos para preencher lacunas.

## Barreiras locais e checkpoint

Cada registro usa staging fixo exclusivo, escrita completa, fsync do arquivo,
link sem substituição do nome final, fsync do diretório, remoção somente do nome
de staging recém-criado e fsync final. Os nomes finais não são sobrescritos pela
referência. Falhas preservam o estágio atingido, sem reparo ou limpeza automática.

Depois de publicar ACK, o writer reconfere identidade, catálogo e bytes do
intent/ACK. Somente então devolve um checkpoint em memória, vinculado aos hashes
dos dois registros e aos pins de raiz/lease locais. A importação é uma chamada
separada: exige esse checkpoint no mesmo writer vivo, reconfere o intent/ACK,
publica import e reconfere os três registros antes de retornar.

Esse checkpoint é uma convenção da referência local, **não um segredo, assinatura
ou capacidade autenticada contra o próprio caller**. Ele impede que esta API
trate mera observação de disco como continuação automática do fluxo. Não é um ACK
de protocolo aceito por um helper nativo ou controlador de produção.

Falha de publicação, evidência inválida, completion desconhecida, resposta perdida,
tentativa repetida ou checkpoint divergente congelam o writer. Chamadas seguintes
falham antes de ler/escrever o journal; `close` apenas fecha FDs. Não há comando
remoto, read automático de recuperação ou cleanup associado ao congelamento.
Mesmo um erro de uso exige revisão, não correção silenciosa da mesma sessão.

## Reinício e durabilidade incerta

O observador separado requer os pins anteriores do pai e do journal e a requisição
local exata. Adquire sua própria lease de forma não bloqueante e confere catálogo
limitado, tipos/modos/proprietário/nlinks, hashes/vínculos e identidades/stamps.
Ele nunca abre writer, grava, importa pins ou devolve checkpoint.

Um ACK completo pode estar visível depois de falha no fsync final ou perda do
retorno. Portanto, o observador classifica os bytes como
`fixture-records-observed-not-recovered`, mesmo quando os três registros estão
íntegros. **Isso não prova a confirmação de durabilidade original, a importação
histórica ou que o caller recebeu o checkpoint.** Não é possível recuperar esses
fatos pela presença de um arquivo que afirma seu próprio sucesso.

O modelo escolhe segurança em vez de disponibilidade: depois de morte do processo,
não existe retomada de escrita, mesmo que a publicação tenha terminado. Um futuro
protocolo de reconciliação precisará de revisão separada; não será habilitado por
essa observação.

## Flags e limites de confiança

Mesmo o resultado `fixture-pins-imported-no-activation` mantém falsos:

- `pin_import_permitted`, `local_pin_ack_verified`, `bootstrap_verified`;
- `authorization_verified`, `original_response_verified`,
  `publication_durability_verified`;
- execução, admissão, replay, cleanup, retomada automática, safe_to_mutate e
  integração com o controlador.

`imported_fixture_pins` descreve somente dados copiados no journal de testes;
não são pins admitidos pelo controlador, nem prova de posse de RAM ou quiescência.
Hashes públicos não autenticam outro root/UID privilegiado. Um ator capaz de
reescrever uma cauda não ancorada pode recalcular seus hashes. A confiança no
pai, no caller e no ambiente continua sendo pré-requisito; as checagens não
impedem todas as corridas privilegiadas ou rollback do armazenamento.

## Testes e evidência

`test-bootstrap-ack.py` usa somente diretórios temporários privados em
`/tmp/opencode`. Cobre:

- intent antes de ACK, ACK antes de import e import explícito sem ativação;
- concorrente recusado, reobservação sem escrita e ausência de reabertura;
- resposta ausente/truncada/estrangeira, contexto/pins divergentes e completion
  desconhecida, com latch de falha;
- todos os estágios de publicação dos três registros e perda de retorno;
- fsync real seguido de erro simulado de conclusão incerta;
- checkpoint ausente/alterado/repetido, corrupção antes do retorno, substituição
  de pai/raiz/lease e registros adulterados/aliases;
- processo filho morto por SIGKILL depois de publicar ACK e antes de devolvê-lo:
  a lease é liberada pelo OS, mas os bytes não recuperam o writer/checkpoint.

Os testes não simulam power-loss real, Android, SELinux ou transporte ADB/su.
Fontes/testes, log, relatório da suíte e hashes estão preservados em
`private-diagnostics/cma-bootstrap-local-ack-01/`.

## Próximo gate

Revisar a ligação entre journal local, contexto e completion **reais**, incluindo
âncora durável independente para reconciliação após reinício e autenticação/
política do caller. Só então projetar ativação explícita separada sob lease e
writer sequencial/dispatcher de produção. Este módulo não foi integrado ao
contrato v3 nem aos observadores/controlador existentes.

Qualquer operação no Quest continua exigindo nova autorização específica.
Aquisição de RAM, layout por alocações retornadas e handoff protegido seguem
pendentes; esta etapa melhora a referência de journal, não a prontidão de boot.
