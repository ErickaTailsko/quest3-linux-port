# Contrato v3 — rascunho encadeado e tipado, sem execução ou admissão

**Modelo puro implementado e testado no host.** Não há writer nativo,
dispatcher, criação de arquivos de sessão, transporte, migração ou operação
no Quest nesta etapa. Os envelopes declaram execution_enabled=false e
producer=host-contract-model; não são mensagens aceitas para uso de produção.

## Escopo e formato

`quest3/cma-identity-query/native-supervisor/chain_v3_draft.py` constrói e
verifica bytes canônicos de um perfil fixo pós-bootstrap. Usa somente dados,
JSON, regex e SHA-256, sem I/O, processos ou consultas ao dispositivo.

O contexto vincula boot/tentativa, binding do dispositivo, helper/módulo,
tamanho do módulo, config/DT stock, release revisado, pins de diretório/lease/
arquivo e compromissos de autorização/ACK de bootstrap. **São vínculos de
dados, não verificação desses fatos:** hash de autorização não é consentimento;
hash de ACK não prova que o bootstrap ocorreu. O contexto dos testes/vetores
é inteiramente sintético, não dados atuais do Quest.

O plano fixa seis papéis e seus argumentos:

| Ordinal | Papel | Dados tipados, não comandos |
|---|---|---|
| 0 | check-environment | Release stock, hashes de config/DT |
| 1 | verify-identity-file | Resource identity-module, hash/tamanho/dev/inode |
| 2 | load-identity-module | Somente q3_cma_identity, inspect=true, attempt esperado |
| 3 | read-identity-report | Resource identity-report e attempt esperado |
| 4 | unload-identity-module | Nome/attempt fixos e resource de evidência de posse |
| 5 | remove-identity-file | Mesmo arquivo fixado e requisito de módulo ausente |

Não há shell, path livre, ELF arbitrário, PFN, pool dedicado, opção de hardening
ou role customizável. IDs de resource terão de ser vinculados por um futuro
dispatcher revisado a objetos exatos; o rascunho não faz esse vínculo runtime.
Os papéis de unload/remove **não autorizam cleanup**, nem presumem posse.
Upload, bootstrap e branches de recuperação estão fora deste perfil normal.

Pins numéricos têm tipos/ranges estritos; diretório/lease/arquivo não podem
se aliasar ou atravessar filesystems no perfil. Há seis nonces de operação
e seis de transporte, distintos entre si e do attempt. Isso evita confundir
nonce de módulo, claim e resposta original.

## Encadeamento

- JSON canônico ASCII, chaves ordenadas, tipos exatos e limites de bytes;
  chaves duplicadas, bool em lugar de inteiro e formatos alternativos são
  rejeitados, assim como schema legado ou execução habilitada.
- Domínios SHA-256 separados para CONTEXT, PLAN, GENESIS, ACTION, CLAIM e RECEIPT.
- Genesis vincula contexto/plano completo, incluindo ordem/argumentos/nonces.
- Cada claim vincula ordinal, operação, transporte, papel/argumentos, contexto,
  plano e **compromisso do recibo anterior**, não apenas da intenção anterior.
- Cada receipt vincula a claim exata e outcome: exit/signal, valor, errno de
  exec, interrupção do supervisor e hashes/tamanhos de stdout/stderr fornecidos.
- Os conteúdos capturados podem ser reconferidos por verify_capture, mas não
  são buscados pela biblioteca. Compromissos não substituem retenção dos logs.

O modelo não escreve recibos nativos v3 nem converte v2. Um formato de produção
terá de preservar captura recuperável/bounded, wait/reap, publicação e provas
de lease/contexto do supervisor, além deste contrato lógico.

Claim sem receipt bloqueia extensão do prefixo. Outcome não zero, sinal, exec
failure ou interrupção encerra o perfil normal; não se pula para cleanup nem
se repete a operação. Recuperação exige decisão/protocolo separado. Mesmo
exit zero não valida semanticamente o relatório de identidade nem os gates
de runtime necessários para unload.

## Checkpoint local e limite de autenticidade

**Uma cadeia de hashes públicos não autentica história.** Um ator que controla
a cauda sem confirmação pode reescrever outcomes e recalcular todos os links,
preservando o plano e uma estrutura aparentemente ordenada.

verify_prefix exige um hash de plano e checkpoint de prefixo que o caller
deverá obter de seu journal local durável/trustado. O checkpoint contém count
e compromisso do último receipt já ancorado (ou genesis para count zero).
Não existe API que avance esse checkpoint automaticamente a partir da cauda
remota ainda não confirmada. receipt_commitment apenas calcula um digest.

Testes explícitos demonstram:

1. Cauda inteira reescrita/recalculada com checkpoint inicial ainda passa como
   estrutura lógica; os seis receipts permanecem classificados não ancorados.
2. Reescrever prefixo coberto por checkpoint local de três receipts é rejeitado.
3. Preservar os três ancorados e reescrever os três seguintes continua apenas
   uma cauda estrutural não autenticada, nunca permissão de retomada.

Checkpoints vinculam os bytes observados/pinados anteriormente; não provam
por si sós que o produtor era confiável ou que ações físicas aconteceram nessa
ordem. Em todo resultado positivo historical_order_proven,
tail_authenticity_verified, foreground_execution_verified,
authorization_verified, bootstrap_verified e identity_report_verified
permanecem falsos. Original ACK, durabilidade, posse de RAM, boot, replay,
cleanup e retomada também não são aprovados.

Os estados draft-prefix, claim-pending, terminal-outcome e draft-complete
descrevem somente o modelo. **draft-complete não é transação stock concluída.**
Nonce/contexto novo produz plano distinto, mas não concede direito a criar
sessão/raiz nova para contornar claims pendentes. O gate persistente global de
admissão/lease ainda precisará ser implementado nativamente.

## Testes e vetores

`test-chain-v3.py` cobre contexto/boot/pins divergentes, troca/pulo/replay de
claims e receipts, payload/role/módulo desviados, argumentos e tipos inválidos,
nonce reutilizado, resultado terminal, limites e checkpoints falsos. Não há
dispatcher fake que simule sucesso de uma operação real: são somente bytes.

`v3-draft-vectors.json` preserva plano, seis pares de envelopes, hashes e
resultado estrutural esperados para futura comparação entre linguagens. São
fixtures sintéticas não executáveis; os testes não as regeneram silenciosamente.
Plan SHA-256 do vetor:
`da23a22376969827763c5777340ab9718364b68f2cd4d2807633169618ade847`.

Suíte completa: **51 aprovações, zero falhas e zero testes ignorados**.
Snapshots/testes e hashes em `private-diagnostics/cma-v3-chain-draft-01/`.
Nenhuma alteração nos fontes C, dois ELFs Android desarmados, módulo kernel
ou Image trim3. Não foi necessário rebuild Android para este modelo Python.

## Próximo gate

Revisar a passagem do rascunho a um protocolo nativo de produção: raiz canônica,
bootstrap/pinagem/ACK durável, claim-before-effect sob lease, política de ações
tipadas e checkpoints locais, sem exatamente-uma-vez fictício. Os observadores
e o controlador congelado não devem começar a admitir ações por ler v3.

Não portar o produtor host-contract-model como interface executável. A versão
live, ABI/filesystem/SELinux, dispatcher, adaptador limitado e nova autorização
específica continuam pendentes. Não enviar binários, consultar/alocar CMA ou
iniciar handoff com base nestes testes.
