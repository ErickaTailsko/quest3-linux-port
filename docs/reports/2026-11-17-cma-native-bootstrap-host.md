# Bootstrap nativo — referência de metadados, sem ativação

> Etapa posterior: [build Android separado e desarmado, verificado offline](2026-11-17-cma-bootstrap-android-build.md).
> Os resultados abaixo registram a etapa host; ativação e runtime continuam pendentes.

**Implementado e validado somente no host: 52 grupos aprovados, zero falhas e
zero ignorados na suíte completa.** Nenhuma operação no Quest, transferência,
consulta, inserção de módulo ou alocação foi realizada. O controlador permanece
desarmado. Os binários anteriores não foram substituídos.

## Contrato implementado

`quest3/cma-identity-query/native-supervisor/bootstrap.c` é um componente separado
do supervisor de execução. O main padrão apenas escreve a mensagem desarmada e
retorna 77. Somente `Q3_BOOTSTRAP_HOST_TEST` expõe a CLI de fixtures; não distribuir
essa variante como ferramenta operacional.

O caller fornece um FD de diretório pai privado previamente fixado, seu path e
dev/inode esperados. A referência confere tipo, proprietário, modo 0700 e identidade
FD/path. **Ela não estabelece a confiança inicial nesse pai**, nem valida boot,
dispositivo, autorização ou hash do próprio executável no Android: esses valores
são dados sintéticos fornecidos pelas fixtures.

A raiz tem nome fixo `q3-identity-registry`. `mkdirat` é a barreira inicial exclusiva:
qualquer objeto existente, inclusive raiz vazia, parcial ou de outro boot/attempt,
impede nova criação. Não há takeover, expiração, reset ou caminho de retry que
ignore esse estado. A lease é criada exclusivamente, com modo 0600, e recebe
`flock(LOCK_EX|LOCK_NB)`; suas identidades e as do pai/raiz são reconferidas.

Sob essa lease, são publicados somente:

- `lease.lock`;
- `bootstrap-intent.json`: requisição canônica vinculada ao contexto local;
- `bootstrap-receipt.json`: requisição, compromisso e pins candidatos.

O compromisso da requisição é SHA-256 de
`b"ERIS-Q3-BOOTSTRAP-HOST-V1\0" + canonical_request`, comparado entre C e Python.
O perfil é `q3-bootstrap-host-reference-v1`; o produtor é
`host-native-bootstrap-reference`. Execução, admissão e ACK local permanecem falsos.
Não são criados `owner.json`, claims de ação ou envelopes v3 executáveis.

Cada registro usa arquivo `.pending` exclusivo, escrita completa, fsync do arquivo,
hardlink sem substituição para o nome final, fsync do diretório, remoção do nome de
staging e fsync final. Uma falha preserva a raiz e o estágio atingido, inclusive
nomes pending ou hardlinks residuais; não existe reparo automático. A referência
não reescreve registros finais, mas isso **não** os torna imunes a outro processo
privilegiado ou do mesmo UID que possa modificar o filesystem.

A resposta `ERIS_BOOTSTRAP_RECEIPT <operation> <receipt_sha256>\n` é enviada apenas
depois da sequência de publicação. Perda da resposta não remove os registros.
Falha no fsync final pode deixar bytes completos visíveis **sem confirmação de
durabilidade**; observar esses bytes depois não recupera essa confirmação.

## Observação separada, sem importação

`bootstrap_receipt.py` valida bytes canônicos, tipos, limites e contexto. O
observador exige a âncora anterior do pai e a requisição local esperada; usa dois
samples de boot injetados para uma observação completa, lease própria não
bloqueante, catálogo limitado e reconferência de identidades/stamps.

Raiz ausente e lease ocupada são observações pontuais, não autorização nem prova
persistente de ausência/quiescência. Estado parcial, objetos extras, symlinks,
hardlinks residuais, permissões divergentes e substituições são rejeitados para
proposta de pins. O observador não cria nem migra arquivos e não é chamado pelo
controlador congelado.

`candidate_pins` é apenas uma proposta para revisão. `pin_import_permitted`,
`bootstrap_verified`, `local_pin_ack_verified`, `authorization_verified`,
`original_response_verified`, `publication_durability_verified`, execução,
admissão, replay, cleanup e retomada automática continuam falsos mesmo após
observação consistente. `reply_matches` confere somente bytes; não persiste ACK.
Hashes públicos e pins não autenticam um produtor privilegiado nem impedem todas
as corridas. A política de pai/ambiente confiáveis continua sendo pré-requisito.

## Evidência de host

`test-bootstrap.py` compila o main desarmado e a variante de fixtures com warnings
como erro, PIE, LTO, stack protector, FORTIFY e RELRO/NOW. Executa somente binários
do host em diretórios temporários privados sob `/tmp/opencode`.

Os testes cobrem: sucesso C/Python, reobservação sem escrita, raiz preexistente
(vazia/arquivo/symlink), contexto/hash/pins divergentes, concorrência, SIGKILL,
perda da resposta, falhas nos estágios de publicação e substituições de pai,
raiz, lease e registros. Também verificam que os metadados novos não permitem
que o writer legado admita uma ação implicitamente.

Snapshots de fontes/testes, builds de host, logs e hashes são preservados em
`private-diagnostics/cma-native-bootstrap-host-01/`. A suíte completa registrada
em `private-diagnostics/host-tests.json` aprovou **52 grupos**. Isso não é teste
de power-loss real, ABI Android, SELinux, armazenamento do Quest ou CFI/SCS de
userspace. Não foi feito build Android deste componente nesta etapa; os dois
ELFs anteriores do supervisor continuam preservados.

## Gates restantes

Antes de qualquer integração operacional: política de pai e âncora inicial,
checagem real de boot/dispositivo/autorização, protocolo durável de ACK/importação
de pins no journal local, ativação explícita, writer sequencial sob lease,
envelope v3 de produção, dispatcher restrito e adaptação de transporte precisam
de revisão e implementação separadas. O main padrão não será habilitado por
mera leitura de um recibo válido.

Build/verificação Android do bootstrap ainda é um gate offline; eventual operação
no dispositivo exige nova autorização específica. Aquisição de RAM, layout por
alocações retornadas, handoff protegido e logs recuperáveis continuam pendentes.
