# Consulta CMA — revisão de transporte e recuperação de estados incertos

> Continuação: [referência host de recibo/lease implementada](2026-11-17-cma-receipt-lease-reference.md).
> Isso não fornece helper remoto nem libera integração/execução no Quest;
> o controlador continua congelando após resultado desconhecido.

**Revisão host concluída com correções; transporte live continua bloqueado.**
Não houve ADB, transferência, carga de módulo, aquisição de páginas ou operação
no Quest. `EXPECTED_MODULE` segue None; não existe adaptador real. O .ko já
construído não foi alterado/recompilado nesta revisão.

## Achado principal: timeout não encerra o comando remoto

O controlador anterior tentava reconciliar presença/relatório e fazer cleanup
imediatamente após uma resposta perdida. Isso é insuficiente: `insmod`, `dd`
ou o shell remoto podem continuar executando após o timeout do cliente.
Ausência momentânea do módulo/arquivo não prova término. Até um relatório
sysfs com token correto pode aparecer antes de o processo de inserção terminar.
Uma inserção tardia poderia ocorrer depois da suposta limpeza.

**Correção:** qualquer término não comprovado bloqueia todos os comandos
posteriores, inclusive leituras e cleanup automáticos nessa transação. Não há
retry, espera seguida de nova tentativa, reconexão automática ou reboot.
O módulo/temporário possivelmente remanescente é retido para revisão, não
declarado limpo. `KeyboardInterrupt` durante transporte recebe o mesmo bloqueio.

Uma resposta *completa*, que prova saída não zero do comando em foreground,
é diferente de resposta ausente/truncada: a primeira pode permitir cleanup
sob os demais gates, mas nunca repetir a inserção.

## Contrato de transporte corrigido, ainda sem adaptador

Novo `quest3/cma-identity-query/transport_protocol.py` contém somente render e
parser puros. `transport(command, token)` deve devolver stdout com marcador
final exclusivo da chamada:

```text
<stdout, preservado exatamente>
ERIS_CMA_DONE <nonce de 32 hex> <status 0..255>
```

O nonce de **comando** é diferente do token de **tentativa do módulo**.
O parser exige marcador único, token exato, posição final, status canônico e
resposta limitada a 1 MiB. Retorno local zero de ADB/su não substitui esse
marcador. Retorno não zero no marcador gera RemoteCommandFailed somente depois
de registrar término comprovado; exceção do transporte não tem essa garantia.

O renderer mantém a ação num subshell foreground, emitindo o status fora dele,
inclusive quando a ação usa exit/set -e. Não executa nada por si só. Esse
marcador comprova término do foreground revisado, **não de árvores arbitrárias
de processos, tarefas background ou trabalho assíncrono do kernel**. O conjunto
de comandos não deve introduzir jobs em background. O protocolo não autentica
outro root nem torna confiável um shell/utilitário malicioso.

## Journal e guards

- Schema local 2: caminho remoto, nonce da tentativa, estado do transporte,
  estado do temporário, contadores de inserção/remoção/delete e eventos com
  nonce por comando. Tokens e boot UUID ficam em diagnóstico privado.
- Cada evento pending é persistido por replace/fsync antes de despachar.
  Somente marcador válido permite completed=True. Resposta inválida tem prefixo
  diagnóstico limitado, explicitamente não verificado.
- Falha de write/replace/fsync é latched na memória e proíbe novos comandos,
  mesmo que o filesystem volte a funcionar. O último journal durável pode
  continuar pending ou não terminal; não se inventa sucesso para compensar.
- Sucesso terminal só é gravado após query e cleanup confirmados. Flags antigas
  de uma fase não promovem uma transação incompleta a sucesso.
- As mutações agora incluem checagem de boot no próprio shell remoto, além
  dos checks host. Antes de rmmod, o shell também exige o token de tentativa
  no relatório atual. Status reservado 125/126 interrompe a automação.
- Preflight de caminho também detecta symlink pendente (`test -L`), não apenas
  alvo existente. Criação sem clobber continua exigindo confirmação explícita.
- CPU masks invertidas, sobrepostas, repetidas, com zeros não canônicos ou
  fora do limite revisado são rejeitadas, mesmo se antes/depois forem iguais.

Esses guards reduzem janelas de erro, mas **não constituem lock atômico contra
reboot ou outro root/gerenciador de módulos**. Nome, hash e nonce não prendem
um inode nem impedem troca de caminho entre checagem e uso.

## Matriz de decisão após falha

| Situação | Estado e decisão automática |
|---|---|
| Hash/consentimento local rejeitado | Nenhum comando enviado |
| Preflight encontra módulo/sysfs/path preexistente | Não assumir posse; não apagar/descarregar |
| Comando completou com status não zero e nonce válido | Falha conhecida; cleanup somente se os demais gates comprovarem posse/boot |
| Status 125/126, guard remoto recusado | Bloqueio para revisão; sem comandos posteriores |
| Timeout, resposta truncada/estranha ou nonce de comando diferente | Uncertain; sem comandos posteriores nem cleanup |
| Ctrl-C durante transporte | Uncertain; preservar evidência e propagar interrupção |
| Journal sem durabilidade comprovada | Bloqueio; usar último estado durável como não terminal |
| Criação do temporário sem confirmação | Não há posse suficiente para delete |
| Relatório de identidade rejeitado, mas íntegro e do token certo, com comandos já encerrados | Pode limpar a própria tentativa sob gates; identidade continua rejeitada |
| Relatório inválido/de outra tentativa ou mudança de boot | Não fazer unload/delete cego |
| Resposta perdida de rmmod ou rm | Não repetir; efeito permanece desconhecido mesmo se possivelmente concluído |
| Processo host caiu e journal ficou pending | Não retomar/repetir; pending pode significar não enviado ou ainda executando |

## Runbook de recuperação — revisão manual, não executado aqui

1. Congelar a tentativa. Não criar outro diretório para contornar o bloqueio,
   limpar contadores, relançar insmod, matar processos remotos ou rebootar.
2. Preservar operation.json, eventual operation.json.new e logs privados sem
   sobrescrever. Registrar qual foi a última ação despachada e qual foi a
   última conclusão comprovada. Journal não terminal não prova ausência.
3. Separar duas perguntas: **o comando remoto antigo terminou?** e **quais
   objetos desta tentativa ainda existem?** Um snapshot de módulos/sysfs/arquivo
   ou o mesmo boot UUID só ajuda na segunda; não responde a primeira.
4. Antes de qualquer reconciliação de dispositivo, revisar um procedimento
   limitado de observação e vincular dispositivo/boot/tokens à tentativa.
   Não há reconciliador live incluído nesta revisão. Observação não concede
   autorização implícita para cleanup, nova consulta ou alocação.
5. Se não for possível comprovar término/quiescência da ação antiga, manter
   estado indeterminado. Duas amostras de ausência, um delay, EOF de ADB ou
   matar o cliente local não resolvem esse gate.
6. Somente após revisão de término, boot, propriedade atual e escopo, elaborar
   cleanup específico para os objetos confirmados. Não usar um journal antigo
   como autorização de rmmod/rm no boot novo. Não repetir tentativa de remoção
   cuja resposta se perdeu sem esclarecer seu resultado.

## Bloqueios restantes antes de um adaptador real

1. **Recibo remoto persistente/quiescência:** o marcador stdout atual pode ser
   perdido com a conexão. Falta mecanismo remoto revisado que permita recuperar
   conclusão da chamada original, sem reexecutá-la. Sua criação/limpeza terá
   efeitos adicionais a revisar. Sem isso, algumas falhas exigem retenção manual.
2. **Exclusão e isolamento remoto:** falta lease/trava e diretório privado
   revisados para serializar gerenciadores e proteger identidade dos arquivos.
   Há TOCTOU entre hash/token/boot e uso; guards não provam exclusão mútua.
3. **Adaptador ADB/su:** selecionar serial explicitamente, preservar quoting,
   separar stdout/stderr, limitar captura, validar marcador remoto e tratar
   deadline/cancelamento local sem alegar cancelamento remoto. Não implementar
   fallback, retry/reconnect automático ou seleção de outro dispositivo.
4. **Revisão/consentimento:** eventual habilitação do hash de binário e execução
   continuam decisões separadas. O consentimento antigo está consumido. Uma
   consulta autorizada não inclui teste pequeno de CMA, payload ou handoff.

## Evidência host

`test-controller.py` simula término tardio de insmod/chunk depois do timeout,
respostas perdidas e sem fence, boot/token recusados dentro da mutação,
interrupção, falhas de replace/fsync e estados preexistentes. Exige zero
comandos depois do primeiro estado incerto/bloqueado e intenção persistida
antes de cada chamada. Falha conhecida com marcador é testada separadamente.

Novo `test-transport.py` usa apenas shell local com printf/exit/false para
conferir status fora do subshell, saída exata, nonce, duplicação/truncamento e
limites. Não usa ADB, su real ou comandos de kernel no host.

Suíte: **46 aprovações, zero falhas e zero testes ignorados**. Nenhum teste
é prova de comportamento real de ADB/su, firmware ou lifetime stock. Os registros
do build com 45 testes permanecem históricos; o módulo de identidade não mudou.
Fontes desta revisão, suíte e revalidação do .ko estão preservados com hashes
em `private-diagnostics/cma-transport-review-01/`. O SHA-256 do módulo continua
`21f62fad44c8ba33c3a16024d87f5c38406cfc20dd374643952b93578cfbd15e`.
