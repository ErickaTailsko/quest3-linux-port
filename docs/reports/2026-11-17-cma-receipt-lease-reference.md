# Consulta CMA — referência host de recibos persistentes e lease

> Continuação: [núcleo supervisor C testado com fixtures no host](2026-11-17-cma-native-supervisor-host.md).
> Ainda não há build Android/Bionic, dispatcher de produção ou integração live.

**Referência filesystem implementada e testada somente no host.** Não é helper
Android, não está conectada ao controlador e não executa ações. Nenhuma operação
ADB, carga, transferência ou aquisição de páginas foi feita no Quest.
O controlador permanece desarmado e continua parando após término desconhecido.

## Escopo implementado

`quest3/cma-identity-query/receipt_store.py` implementa armazenamento/observação
de claims, recibos e lease em diretório privado. Não contém subprocess, ADB,
dispatcher, limpeza, retomada ou chamada de módulo. O dispatcher/supervisor
real permanece um componente ainda a implementar/revisar.

Uma Intent vincula boot UUID, tentativa, nonce de operação, SHA-256 da ação
exata e SHA-256 do módulo. O contexto inicial também fixa device/inode do
diretório **e do arquivo de lease**; reconexão não deve redescobrir esses valores
num caminho potencialmente substituído e tratá-los como identidade nova.

No diretório 0700, de propriedade do usuário efetivo do helper:

- lease.lock: arquivo 0600 permanente, nunca removido ou explicitamente
  desbloqueado pela biblioteca;
- owner.json: dono lógico persistente da sessão/boot/módulo e identidade dos
  objetos filesystem; nenhuma tomada por idade, timeout ou PID;
- claim-OP.json: intenção imutável, persistida antes de devolver um ticket
  que um futuro supervisor poderia usar para despachar;
- done-OP.json: resultado, stdout em base64 com tamanho/SHA-256 e vínculo
  completo com a Intent, após término foreground afirmado pelo supervisor;
- stage-NONCE.json: publicação intermediária; se restar após falha, bloqueia
  admissão/recuperação automática, sem remoção ou overwrite silencioso.

Publicação usa criação exclusiva, fsync do arquivo, link sem substituição,
fsync do diretório e retirada do staging com novo fsync. Uma falha deixa
evidência parcial e bloqueia o objeto local. Novas instâncias rejeitam staging,
claims pendentes, metadados inválidos e identidades divergentes. Não há fallback
que omita fsync, hardlink ou validações quando o filesystem não os suporta.

O código exige arquivos regulares 0600 do dono esperado e um único hardlink,
O_NOFOLLOW, JSON limitado sem chaves duplicadas, hash/tamanho de stdout coerentes
e operações relativas ao dir-fd. O limite de stdout desta referência é 64 KiB;
ultrapassá-lo é falha, não autorização para truncar uma evidência válida.

## Invariantes de admissão e observação

1. Uma operação já claimed nunca é reexecutada, mesmo quando possui recibo.
2. Claim sem recibo bloqueia **qualquer nonce novo** nesse store. Ausência de
   receipt pode significar que a ação não começou, segue ativa ou terminou
   antes da falha do supervisor. Não escolher uma dessas hipóteses por timeout.
3. Owner persistente recusa outro boot/tentativa/módulo, mesmo com flock livre.
   Não há expiração, reset ou retirement automático. Uma nova pasta também não
   deve servir para contornar a raiz canônica que um helper real terá de fixar.
4. Somente operações da mesma sessão e sem pendências anteriores podem obter
   novo ticket. Isso é admissão no ledger, **não autorização para executar**:
   políticas, consentimento e gates do controlador são externos à biblioteca.
5. Mesmo resultado aceito mantém safe_to_mutate, automatic_resume_allowed,
   tree_quiescence_proven, ownership_acquired e boot_ready falsos.

| Estado observado | O que permite concluir |
|---|---|
| lease-held | Há uma referência com flock; não declarar a ação encerrada |
| claim-without-receipt | Intenção existe; efeito/término permanecem indeterminados |
| other-claim-without-receipt | Outro nonce não contorna uma pendência da sessão |
| completed-foreground | Recibo íntegro recuperado com lease livre naquele instante, sob contrato do supervisor |
| not-claimed-observation-only | Claim não observada; não autoriza reenviar uma chamada possivelmente atrasada |
| unknown/erro | Metadados, identidade, publicação ou acesso inconsistentes; reter para revisão |

**Não se afirma exactly-once de efeitos.** Existe uma janela legítima entre
executar a ação e registrar seu resultado. O projeto prefere manter esse
resultado desconhecido a repetir uma operação que pode já ter acontecido.

## Lease herdada e contrato de término

A referência usa flock não bloqueante por open-file-description no Linux.
Um supervisor futuro pode passar o mesmo fd ao foreground revisado. O ticket
fecha somente sua referência: **não chama LOCK_UN**, que soltaria a trava
compartilhada mesmo se o filho continuasse ativo. O arquivo da trava não deve
ser apagado/recriado; a identidade de inode fixada rejeita substituições vistas.

Ticket.complete é uma **afirmação de um supervisor confiável**, que deverá
esperar/reapear o foreground real e manter a lease durante execução/publicação.
A biblioteca de armazenamento não sabe se esse wait ocorreu, não consulta PID
e não prova morte de descendentes arbitrários ou trabalhos assíncronos no kernel.
Mesmo recibo presente não vence uma lease ainda ocupada na observação.

O teste de herança verifica fechamento da referência do supervisor com um
filho mantendo o fd; um teste separado usa morte real do processo sem receipt.
Isso não é simulação de todo o processo ADB/su/Android nem prova de quiescência
runtime do módulo. Background jobs não entram no contrato proposto.

## Recuperação proposta, sem integração automática

Depois de perda de resposta, o controlador atual continua congelado. Um futuro
observador, em escopo separado, deverá vincular journal local, boot atual,
raiz/lease previamente fixadas, owner, claim e receipt à **mesma chamada**.
Recuperar stdout/retorno não dispara o dispatcher nem altera o journal antigo
para fingir que houve confirmação original.

Lease livre isoladamente, diretório desaparecido, nonce novo, PID morto, duas
amostras de ausência ou tempo decorrido não autorizam repetir/limpar. Recibo
recuperado pode orientar a próxima revisão de cleanup, nunca concedê-lo sozinho.
Não há API de takeover/retirement nem remoção de módulo/temporário nesta etapa.

## Testes e evidências

`quest3/cma-identity-query/test-receipts.py` exercita arquivos e flock reais em
diretórios temporários privados do host, sem dispositivo:

- resultado reaberto após fechar o store, inclusive status não zero;
- duas referências concorrentes, receipt presente com lease ocupada e fd
  herdado por filho controlado por pipes, sem sleeps/poll loops;
- os._exit do supervisor deixando claim sem receipt e bloqueio de nonce novo;
- write/fsync/link/unlink falhando durante publicação, claim não durável que
  nunca devolve ticket, staging e metadados preservados;
- JSON truncado/duplicado, output corrompido, symlink, permissões/hardlinks,
  receipt órfão, tamanho excessivo e substituição de diretório/inode da lease.

Suíte completa: **47 aprovações, zero falhas e zero testes ignorados**.
O .ko e o fonte C da consulta não mudaram; os registros anteriores de 45/46
testes permanecem históricos. Snapshots/testes e hashes desta etapa ficam em
`private-diagnostics/cma-receipt-lease-reference-01/`.

## Gates ainda abertos

- Portar/revisar um supervisor nativo para o Android stock; Python no Quest
  não foi presumido. O wait/reap, herança de fd, sinais e recibo antes da
  resposta precisam ser implementados/testados nesse ambiente.
- Fixar raiz canônica sob pai confiável, proteção de caminhos/arquivo do módulo,
  pinagem desde o handshake inicial e integração do ledger com todos os efeitos.
  O protótipo não impede outro root não cooperante ou um gerenciador que ignore
  a lease; checks de inode não são exclusão atômica contra tais agentes.
- Validar filesystem/SELinux, durabilidade e semântica de locks no stock; os
  testes host não substituem isso e não autorizam mudar SELinux/proteções.
- Projetar observação/reconciliação separada sem replay, adaptador ADB/su limitado
  e nova autorização específica antes de qualquer operação no Quest.

Portanto, recibo/lease deixaram de ser apenas um desenho abstrato, mas o gate
**de implementação e validação remotas permanece aberto**. Não habilitar o hash
do módulo nem reutilizar consentimento antigo em função destes testes host.
