# Bootstrap/catálogo v2 — observação explícita, sem admissão ou replay

> Continuação: [rascunho v3 encadeado/tipado e checkpoints locais](2026-11-17-cma-v3-chain-draft.md).
> É um modelo não executável; writer/bootstrap nativos e admissão continuam pendentes.

**Revisão concluída com observador de referência no host.** Nenhum helper foi
executado no Android, enviado ao Quest ou conectado ao controlador. Bootstrap
e writer de catálogo nativos continuam pendentes; o dispatcher permanece
desarmado. Não houve aquisição de páginas nem alteração dos binários anteriores.

## Achados e decisão

1. **Recibos v2 não provam ordem.** A Intent vincula boot, tentativa, operação,
   action_sha256 e módulo, mas não contém ordinal/predecessor. Vários recibos
   íntegros não provam que preparação, consulta e cleanup ocorreram na ordem
   requerida. Trocar a ordem do manifesto não altera essa ausência de evidência.
2. **Recibo visível não recupera o ACK original.** Um arquivo completo pode
   estar visível depois de falha no fsync final ou perda da resposta. Seus bytes
   podem orientar perícia, mas não provam confirmação da publicação/transporte.
3. **Bootstrap não pode confiar em si mesmo.** Aprender novos inodes a partir
   de um path substituído e do owner contido nele não restaura a pinagem antiga.
   Ausência de owner/claim é ambígua, não autorização para recriar diretórios.

Decisão desta etapa: **aceitar v2 somente para observação explícita de registros
esperados**, nunca como protocolo de admissão sequencial. O ledger v1 permanece
inalterado e rejeita recibos v2. Não existe fallback entre versões.

Antes de um writer/dispatcher sequencial, revisar um novo envelope versionado
com ordinal, compromisso do predecessor, papel da operação e digest dos
argumentos tipados/autorizados. O fingerprint host-fixture-v1 não é uma política
de comandos stock. Não acrescentar esses significados retroativamente ao v2
nem transformar catálogos antigos em sessões executáveis.

## Implementação de observação

`quest3/cma-identity-query/native-supervisor/v2_catalog.py` fornece observe
somente para o host. Perfil explícito: **owner1-claim1-native2-observation-only**.
Os envelopes owner/claim de schema 1 são comuns ao protótipo C; o receipt é
schema 2. Isso não é migração do writer nem alteração do protocolo Android.

O caller precisa fornecer manifesto local esperado, pinagem anterior dos
inodes de diretório/lease e uma fonte de amostras de boot. A biblioteca não
descobre operações autorizadas a partir dos arquivos remotos. Nos testes, a
fonte de boot é injetada e sintética: não é validação do boot real do Quest.

A observação:

- confere a primeira amostra de boot e root/lease por inode, dono efetivo,
  tipo, permissões 0700/0600 e número de links dos arquivos;
- abre por dir-fd com O_NOFOLLOW/O_NONBLOCK e tenta flock exclusivo sem espera;
  lease ocupada termina a observação sem ler/publicar resultados do catálogo;
- exige owner/claims canônicos exatamente iguais ao contexto/manifesto local;
- limita a 128 operações, 258 entradas, 2 KiB por owner/claim e menos de 190 KiB
  por recibo; valida base64, tamanhos, hashes, término e flags via parser v2;
- rejeita operação inesperada, receipt órfão, schema diferente, staging de
  qualquer protótipo, symlinks, FIFO, hardlinks e metadados inválidos;
- retém sua própria lease durante a leitura, recolhe segunda amostra de boot
  e revalida root/lease, nomes, inodes, tamanho, mtime/ctime de cada arquivo;
- descarta **todos** os recibos recuperados se um erro tardio invalidar o
  catálogo. Não retorna uma aprovação parcial de um catálogo inconsistente.

Não há create, claim, dispatch, reset, migrate, retire ou cleanup nessa API.
Ela não escreve conteúdo, journal ou respostas remotas. flock afeta o estado
de locks do kernel e leituras podem atualizar atime: não se afirma operação
sem efeitos. São observações no host, sem transporte real.

## Estados e limites de conclusão

| Estado | Significado restrito |
|---|---|
| unknown | Contexto, metadados, leitura ou publicação inconsistentes |
| lease-held | Não foi possível adquirir a lease; não inferir término |
| claims-unresolved | Existe intenção esperada sem recibo íntegro observado |
| partial-catalog | Há operação esperada cuja claim não foi observada |
| receipts-observed | Todos os registros esperados combinam nesta observação |

catalog_verified é consistência de conteúdo/manifesto, **não validação da
sequência ou permissão de executar**. exclusive_observation_acquired registra
a aquisição desta observação; não promete lease livre após o retorno. Duas
amostras de boot não são uma trava contra reboot/ABA/outro root.

sequence_verified, bootstrap_verified, original_response_verified,
publication_durability_verified, safe_to_mutate, replay_permitted,
cleanup_permitted, automatic_resume_allowed, tree_quiescence_proven,
ownership_acquired e boot_ready permanecem falsos em todos os caminhos.

Saída normal não zero, sinal e erro de exec continuam sendo resultados
recuperáveis, não consulta CMA aprovada. Os bytes de stdout/stderr não são
interpretados como prova de identidade runtime do pool nem posse de RAM.

As verificações finais detectam algumas corridas observadas, mas não tornam
imutável um filesystem controlado por outro root. Pai confiável, atores
cooperantes com a lease e prova de procedência do helper continuam pressupostos
de uma implementação remota revisada. A interrupção fecha somente os FDs desta
observação, sem LOCK_UN compartilhado, matar processos ou alterar a tentativa.

## Contrato proposto para bootstrap futuro — ainda não implementado

1. **Âncora anterior à sessão:** definir pai/raiz canônicos e lease global do
   helper, sob política de dono/permissões e sem traversal de symlinks. Uma
   pasta nova por nonce não deve contornar uma sessão/claim pendente.
2. **Intenção local antes de criar:** vincular dispositivo selecionado, boot,
   binário do helper/módulo e nonce num journal durável, antes de qualquer
   mutação de bootstrap. Criar metadados no Quest já seria um novo escopo de
   operação; o consentimento de download de NDK não cobre isso.
3. **Handshake de pinagem antes da primeira ação:** criar/publicar metadados
   exclusivos, validar resposta e persistir pins/contexto localmente antes de
   admitir uma ação. Se a resposta/persistência se perder, congelar; não
   redescobrir inodes a partir do owner recém-encontrado e chamá-los de confiáveis.
4. **Sem retomada por idade/PID:** owner e claim pendentes sobrevivem à lease
   livre. Sem TTL, takeover, exclusão automática ou reaproveitamento em boot novo.
5. **Admissão separada da observação:** catálogo de ações exige sequência e
   argumentos tipados sob consentimento específico. Um receipt recuperado não
   reabre o controlador congelado e não substitui seu fence de término original.
6. **Retirement explícito:** só projetar após comprovar resultado/limpeza da
   sessão e revisar os objetos exatos. Não apagar staging/claim para fazer um
   catálogo inválido parecer pronto.

Esses requisitos não constituem uma autorização de bootstrap no dispositivo.
Falta portar/implementar o protocolo no supervisor nativo, revisar APIs/ABI,
filesystem/SELinux e o adaptador limitado antes de qualquer pedido de execução.

## Testes e preservação

`test-v2-catalog.py` cobre arquivos/leases reais do host e fixtures de catálogo:
manifesto limitado, legado, múltiplas operações, ordem não comprovada, owner e
claim divergentes, staging, corrupção, tipos de arquivo, trocas de inode/boot,
interrupção e ausência de criação/mudança de conteúdo ou vazamento de FDs.

`test-supervisor.py` agora observa explicitamente recibos produzidos pelo C
real em fixtures locais: exit/signal/exec failure, saída binária, resposta
perdida, lease ativa, SIGKILL e claims não resolvidas. Também confere o caso
de recibo visível após hook de erro no fsync final: observa bytes sem validar
ACK/durabilidade ou liberar retomada. O ledger v1 continua retornando unknown
para os mesmos recibos nativos.

Suíte completa: **50 aprovações, zero falhas e zero testes ignorados**.
Evidências e snapshots com hashes em `private-diagnostics/cma-v2-catalog-review-01/`.
Fontes C/headers e os dois ELFs Android desarmados não mudaram; nenhum rebuild
Android foi necessário para esta camada Python de referência. O kernel, Image
trim3 e módulo da consulta também foram preservados.

Próximo marco seguro: revisar o envelope de admissão/encadeamento e bootstrap
nativo, mantendo este observador separado e o dispatcher desarmado. Nenhuma
autorização anterior foi reutilizada; não chamar alocadores nem ampliar
sondagens de RAM com base em um catálogo de recibos.
