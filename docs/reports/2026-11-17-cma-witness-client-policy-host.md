# Witness — identidade e política do cliente, somente fixtures de host

**Wrapper de cliente implementado e testado localmente: 58 grupos aprovados,
zero falhas/ignorados.** Nenhuma conta, serviço, rede, chave operacional ou
operação no Quest foi configurada/executada. Controlador, witness anterior e
artefatos Android/kernel permanecem preservados.

## Escopo e fronteira real

`native-supervisor/witness_client_policy.py` acrescenta um front door de fixtures
ao `FixtureWitness` existente. Ele não é um servidor e não implementa transporte.
Os testes têm acesso às chaves no mesmo processo: não demonstram isolamento real
entre cliente e witness.

**A API raw do FixtureWitness continua sendo uma API de testes de baixo nível.**
Ela não foi transformada em endpoint autenticado e pode ser chamada diretamente
por quem controla o processo da fixture. Um deployment real teria de expor
somente o gate revisado e manter chave, banco e política fora do domínio do
cliente. Não há tal deployment nesta etapa.

## Política fixada antes da requisição

O scope canônico vincula:

- fingerprint de uma chave pública Ed25519 do cliente;
- fingerprint da chave pública Ed25519 do witness, distinta da chave do cliente;
- pending, checkpoint e contexto exatos;
- ações permitidas: `publish`, `observe` ou ambas, sem duplicatas/ação livre.

As chaves e o scope são injetados pelo owner confiável da fixture, não aprendidos
da mensagem recebida. A fonte/assinatura de autoridade da política, revogação,
rotação, provisionamento, namespaces e armazenamento independente de produção
continuam pendentes. Construir bytes de scope não estabelece sua autorização.

`publish` autoriza, na fixture, somente a notarização daquele vínculo de digests;
`observe` permite somente observar o mesmo vínculo. Nenhuma ação contém shell,
path remoto, módulo, PFN ou operação de boot. Não é autorização para executar o
bootstrap ou repetir uma operação no dispositivo.

## Três mensagens autenticadas e domínios separados

| Mensagem | Quem assina | Vínculos conferidos |
|---|---|---|
| challenge | Witness | Hash do scope e nonce da sessão |
| submission | Cliente | Scope, challenge exato, sessão, ação, requisição e identidade do cliente |
| response | Witness | Submission exata, scope/challenge, cliente/witness, ação e declaração interna |

O perfil é `q3-witness-client-policy-host-v1`, sempre de fixtures, com execução
desabilitada. Os domínios de assinatura de challenge/submission/response são
distintos. Tipos, campos e JSON canônico são conferidos sem aceitar extensões
livres ou chaves aprendidas da resposta.

O nonce de sessão padrão vem de `secrets.token_hex(16)`. O override é destinado
somente a testes. A requisição de witness deve usar nonce diferente da sessão.
O caller futuro ainda precisará gerar/comprometer seu nonce de requisição e
vincular a resposta à tentativa correta; uma assinatura não prova frescor de
produção por si só.

O wrapper verifica assinatura do cliente, scope e sessão antes de delegar a
publish/lookup. O nonce da requisição é reclamado em memória **antes** da chamada
ao witness. Reutilização, inclusive entre publish e observe, ou mais de 32
submissions na mesma sessão congelam gate e handle de witness.

A declaração interna continua distinguindo `publication-confirmed` e
`record-observed`. A resposta externa assinada acrescenta o vínculo à submission
e ao challenge; apenas uma declaração interna coincidente não satisfaz uma
resposta de outra sessão/ação.

## Falhas e limites de replay

Erro de inicialização validada, assinatura/política, nonce, delegação ou retorno
congela a instância e o witness associado. Não há consulta automática, retry ou
rotação de sessão para corrigir erro. Acesso ao challenge também falha fechado
se a instância já estiver congelada. Fechamento apenas delega o close local.

Os testes usam trace de SQLite para confirmar que requisições não autenticadas,
fora do scope ou repetidas não chegam sequer a fazer consultas delegadas. Após
congelamento, não há reads/assinaturas seguintes por esse handle.

Falha depois do COMMIT do witness, mas antes do retorno externo, deixa o vínculo
possivelmente publicado sem resposta scoped entregue. Uma abertura explícita de
observador pode produzir **nova observação**, não reconstruir a resposta original
ou retomar automaticamente o gate antigo.

O conjunto de nonces reclamados existe somente em memória. Uma sessão nova tem
challenge novo e rejeita o envelope antigo. Porém, o teste força a reutilização
do nonce de sessão em outra fixture com as mesmas chaves/scope: o challenge é
recriado e o envelope antigo pode voltar a verificar. Isso demonstra por que
o override não é configuração operacional e por que a referência **não prova
anti-replay durável, monotonicidade ou proteção contra rollback**.

## Resultados e gates não fechados

A verificação positiva atesta assinaturas dos bytes do cliente/witness e
coincidência do scope/sessão fornecidos. Mantém falsos origem autorizada da
política, frescor de produção, isolamento, rollback/não-equivocação, entrega
original, ACK/bootstrap/autorização reais, pin import, execução, admissão,
replay permitido, cleanup, recuperação de writer e retomada automática.

Não há integração com o controlador, publisher de âncora externa ou journal
operacional. A política não previne que outro owner configure outra instância
com chave/scope reaproveitados; as limitações de forks do witness permanecem.

## Testes e preservação

`test-witness-client-policy.py` cobre round-trip publish/observe, chaves com papéis
distintos, assinaturas/domínios inválidos, ações/digests fora do scope, sessão
estrangeira, nonce repetido/capacidade, resposta de outra submission/ação,
adulteração de payload/canonicalização, inicialização inválida e perdas após
resultado/antes de retorno. Inclui o caso negativo de sessão deliberadamente
reutilizada, sem alegação de proteção durável.

São usados somente SQLite e `cryptography` já presentes no host, com chaves
efêmeras em memória; nenhum pacote foi instalado. Fontes, logs, vetores públicos
assinados sem chave privada e suíte/hashes são preservados em
`private-diagnostics/cma-witness-client-policy-host-01/`.

Próximo gate: revisar origem/provisionamento de chaves e política, isolamento da
fronteira de serviço e mecanismo preventivo de rollback/não-equivocação, antes
de considerar deployment separado. Nenhuma autenticação desta referência
habilita operação no Quest ou substitui nova autorização específica.
