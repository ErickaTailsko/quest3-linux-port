# Estado consolidado

## Conclusão

**Atualização de 2026-11-19:** 69 grupos host aprovados, zero falhas/ignorados.
Validador offline de Image/initrd/DT em três alocações fornecidas implementado,
com bounds, protocolo ARM64, DT estático e rewrite somente de chosen. Endereços
de teste são fictícios; loader fixo preservado, nenhum alocador chamado ou boot
alternativo realizado. O usuário escolheu avançar neste layout e manter o
monitor operacional bloqueado pela âncora independente ainda não definida.
[Layout e próximos gates](reports/2026-11-18-returned-allocation-layout-host.md).

Núcleo C aritmético separado agora testado com UBSan e 2.000 casos diferenciais
seeded contra Python. Consulta por máscara considera os três destinos completos,
inclusive prefixo/padding; zero não comprova página utilizável e erros preservam
saídas. Não faz parsing de DT/header, validação de IDs/posse ou aliases entre
recursos de trabalho. Header não incluído pelo loader; sem build kernel/Android,
alocação ou operação no Quest. Próximo gate: representação/lifetime e plano de
staging/descritores antes de qualquer adaptador desarmado.
[C host e limites](reports/2026-11-18-returned-layout-c-core-host.md).

Modelo host de staging/descritores agora cobre snapshots por página, zero-fill,
IDs/contexto, aliases entre fontes/descritores/código/tabelas/scratch e exclusão
dos destinos completos. Produz/verifica somente bytes de descritores de fixtures,
sem seguir ponteiros físicos. Registros retidos coincidentes não comprovam
lifetime. Cenário trim3 + initrd reais e DT/recursos sintéticos: 8.317 sources,
33 descritores e 3 auxiliares somam ~32,63 MiB além dos 36 MiB de destinos,
~68,63 MiB contabilizados antes de outros custos. Sem alocador, build alvo,
integração, transferência ou operação no Quest. Próximo gate: comparar estratégias
de staging e orçamento antes de adaptar o loader.
[Staging e orçamento](reports/2026-11-18-relocation-staging-plan-host.md).

Comparação offline concluída: relocação ~68,63 MiB versus direto hipotético
~36,02 MiB com buffer de 4 KiB e transição igual assumida. Diferença ~32,61 MiB
em recursos contabilizados, não pico medido; page cache/outros custos excluídos.
Ambas mantêm Image CMA de 32 MiB. Direto exige posse/mapping/isolamento antes de
escrever e um caminho sem cópia novo/revisado; writer e streaming não existem.
Próximo gate é revisão de contrato/lifetime/cache/falhas, não ativação runtime.
Nenhum destino adquirido ou comando no Quest.
[Comparação e limites](reports/2026-11-18-staging-comparison-host.md).

Contrato documental da hipótese direta revisado: handles reais versus registros,
mapping/isolamento antes da escrita, streaming limitado, selagem de bytes versus
clean até PoC e falhas conhecidas versus conclusão incerta. Readback no mesmo
mapping não prova visibilidade após cache/MMU off. Nenhuma implementação/gate
runtime liberado; permanecem 64 grupos. Próximo passo: traços de fases/falhas
somente no host, sem writer ou integração.
[Contrato e matriz de falhas](reports/2026-11-18-direct-staging-contract-review.md).

Traços do contrato direto agora verificados por função pura de host: um pedido/
buffer por vez, progresso de arquivo/zeros, claims por fase, seal/boundary/clean
e estados terminais distintos para erro conhecido, erro irreversível e incerteza.
Recusa reads/cleanup/retry após falha, sem API de execução/liberação. Mesmo o
traço completo mantém posse, autorização, cache validado e boot_ready falsos.
65 grupos aprovados, nenhum destino adquirido ou comando no Quest. Próximo gate:
confrontar offline contrato com fontes/ABI stock e primitivas de mapping/cache.
[Traços, testes e limites](reports/2026-11-18-direct-staging-traces-host.md).

Confronto offline com fontes/ABI stock concluído, sem novo grupo de testes:
CMA/buddy têm pares exportados; `cma_release` não valida ownership e
`free_pages_exact` retorna void. Helpers `__flush_dcache_area` e
`__clean_dcache_area_poc` existem no fonte mas não na tabela de exports fornecida;
`flush_dcache_page` exportada só altera flag nesta árvore, não faz clean imediato.
Mapping/lifetime/PoC e entrada continuam abertos, sem adaptador/build/operação
no Quest. Próximo gate: alternativas de publicação de cache e fronteira real de
irreversibilidade, somente host. Permanecem 65 grupos aprovados.
[ABI, fontes e lacunas](reports/2026-11-18-direct-staging-stock-abi-review.md).

Revisão offline de publicação/fronteiras concluída: helper local de cache é só
candidato a estudo de prova, não implementação aprovada. Freezer pode congelar
observador; USB desconecta antes da PHASE 11; tentativa opcional de desativar
watchdog seguro sem inversa também a antecede. `release_devices` não comprova
rollback completo, e retorno de device shutdown não prova DMA quieta. Nenhum
gate runtime liberado; permanecem 65 grupos. Próximo passo: contrato por ranges/
última escrita de payload, código e tabelas, sem helper ou mudança no loader.
[Cache e fronteiras](reports/2026-11-18-cache-publication-boundary-review.md).

Ledger host de cobertura por intervalos implementado separadamente: seis recursos
de fixture (payloads/código/PGD/PUD), bytes inicializados, linhas dirty, claims de
PoC/I-cache e última escrita. Writes posteriores invalidam cobertura; checkpoint
não é selo permanente. Fronteiras de observação/transporte/efeitos sem inversa
são distintas e incerteza bloqueia eventos seguintes. 66 grupos aprovados,
nenhum helper/writer ou operação no Quest. Próximo gate: vínculo host entre layout,
traço de fases e ranges, sem admissão runtime ou relaxar selagem.
[Cobertura e última escrita](reports/2026-11-18-cache-publication-ranges-host.md).

Vínculo host implementado separadamente: layout/recursos exatos e uma timeline
de fases/publicação, com writes de payload derivados das conclusões de cópia/
zeros. Inicialização dos seis recursos antes de seal e cobertura no ponto de
final-clean exigidas; sem reabrir selagem. 67 grupos aprovados, incluindo trim3/
initrd reais com DT/recursos sintéticos e buffer declarado de 64 KiB. O traço
completo trim3/4 KiB excede o limite desta composição e não foi validado por ela.
Nenhuma admissão runtime/helper/writer ou operação no Quest. Próximo gate:
evidências reais de lifetime e contrato ABI/CFI do eventual helper, sem port live.
[Vínculo, limites e testes](reports/2026-11-18-staging-binding-host.md).

Revisão offline de evidências lifetime/ABI do eventual helper concluída, sem novo
grupo: lookup reserved_mem não incrementa referência; lock de memória até shutdown
não é lease genérico e admite ciclo potencial com CPU hotplug. ELF histórico tem
três calls diretos ao helper local, BTI e corpo leaf sem clobber x18; isso não
prova novo alvo indireto CFI, cache real ou handoff. Nenhum helper/gate runtime
liberado; permanecem 67 grupos. Próximo gate: critérios de aceitação do contrato
leaf direto antes de implementação; lifetime real continua independente.
[Lifetime e ABI/CFI](reports/2026-11-18-lifetime-helper-abi-evidence-review.md).

Contrato de aceitação do eventual helper leaf definido (L01–L14): chamada direta,
ABI estreita, CFI/SCS/BTI/PAC e ranges, com evidências e controles de rejeição.
Novo perfil exige proteção PAC de retorno; helper histórico não é controle
positivo completo. PASS de ABI não comprova PoC ou lifetime. Nenhum helper ou
verificador novo nesta etapa, permanecem 67 grupos e ~40% subjetivos. Próximo
gate: verificador estático read-only com fixtures negativas, sem implementação
de helper ou alteração do loader.
[Contrato e critérios](reports/2026-11-18-cache-leaf-acceptance-contract.md).

Verificador read-only parcial implementado: parser ELF/relocações bounded,
subconjunto BTI/registradores/PAC por controle de fluxo e aritmética uint64 de
ranges. Fixtures negativas, 200 mutações ELF e 500 casos aritméticos seeded;
68 grupos aprovados. ELF histórico é REJECT em L08, não controle positivo novo.
Resultado global sempre PENDING/REJECT; procedência/ABI C/CFI dos callers,
cache e lifetime não são inferidos. Sem helper/build/alteração de loader ou
operação no Quest; estimativa global ~40% permanece subjetiva. Próximo gate:
revisão dos limites e vínculo de procedência/ABI de callers/imports.
[Verificador e limites](reports/2026-11-19-cache-leaf-static-verifier-host.md).

Revisão do parser/callers concluída: nomes agora têm cache/limites individual e
cumulativo; queries de caller usam sweep ordenado, com teste de 10.000 casos.
Auditoria pontual do ELF histórico: 72 versões = 71 indefinidos + module_layout,
CRCs compatíveis e namespace VFS declarado. Quatro imports SCM vêm do provider
modular qcom-scm, não de vmlinux. Hashes/.cmd atuais não provam build reproduzido
ou ABI completa; contrato continua PENDING/REJECT. Permanecem 68 grupos, sem
helper/build/loader/dispositivo. Próximo gate: checagens reutilizáveis de
conteúdo/interfaces/política de imports, ainda read-only.
[Limites e evidência de callers/imports](reports/2026-11-19-cache-leaf-parser-caller-evidence-review.md).

Checagem reutilizável de imports/conteúdo implementada como API pura: versões/
indefinidos, CRC/provedor/tipo/namespace, licença/dependências declaradas, política
explícita e hashes. Substituição coerente de todos os inputs ainda não prova
build/autorização; resultado global sempre PENDING/REJECT. 69 grupos aprovados.
Metadados históricos consistentes não revogam REJECT PAC do leaf. Sem helper,
build, loader ou Quest. Próximo gate: pacote de evidências e plano de build
offline isolado do futuro candidato, antes de implementar/construir helper.
[Imports, política e limites](reports/2026-11-19-cache-leaf-import-policy-host.md).

Plano do futuro build isolado e pacote de evidências especificados (B0–B5):
inputs stock fixados, O=/M= novos, init de recusa sem endpoint, retenção de
caller sob Full LTO e política própria de imports. Nenhum fonte de candidato,
diretório de build, helper ou build criado/executado; permanecem 69 grupos e
~40% subjetivos. Próximo gate B0: revisar proposta de fontes/caller/linha/retorno
antes de implementação, sem loader, carga de módulo ou operação no Quest.
[Pacote e plano isolado](reports/2026-11-19-cache-leaf-isolated-build-plan.md).

Revisão textual B0 (2026-11-23): `cache_line_size()` usa máximo/CWG, não passo
DminLine. `read_sanitised_ftr_reg` é export público GPL presente no symvers e
oferece hipótese melhor para geometria sistêmica. Retenção __used/noinline não
foi comprovada no ELF; B0 permanece PENDING, sem candidato/build/Quest.
[Revisão B0](reports/2026-11-23-cache-leaf-b0-source-review.md).

Revisão adicional B0: entrada de CPU passa pela atualização do CTR; capabilities
finalizadas não bastam como prova de imutabilidade. Geometria externa não cabe
implicitamente na ABI v1. Config/Makefile favorecem ausência de tail-call, sem
prova do ELF. Próximo gate documental: proposta versionada de ABI/geometria,
sem candidato/build/Quest; B0 permanece PENDING.
[Hotplug e ABI](reports/2026-11-23-cache-leaf-b0-hotplug-abi-review.md).

Draft documental de ABI/geometria separado de v1: terceiro argumento de passo,
sem adoção ou mudanças em fontes/verificadores. Distingue passo mínimo S do
envelope de efeitos G para ownership; o arredondamento por S sozinho não prova
containment numa CPU com linhas maiores. B0 segue PENDING por contexto,
geometria/erratas, estabilização e artefato. Sem candidato/build/Quest.
[Draft de geometria explícita](reports/2026-11-23-cache-leaf-explicit-geometry-abi-draft.md).

Revisão de 2026-11-25: APIs públicas cpus_read_lock/trylock/unlock presentes no
symvers, hipótese apenas de seção pré-shutdown delimitada. Não manter lock
através de shutdown; envelope G, operação/erratas, contexto e ordem de locks
seguem pendentes. B0 PENDING, sem candidato/build/Quest.
[Envelope e pré-shutdown](reports/2026-11-25-cache-leaf-preshutdown-envelope-review.md).

Atualização de build: novo candidato QMP compilado com sucesso, com provedores
AOSS/QMP embutidos; verificador de artefatos e layout aprovados. Image SHA-256
`b1cca22c48f2a22e67229cc99b9bcd0778f019ad759130d142e6887a476e7e5b`.
É separado do candidato original e **não foi iniciado no aparelho**.
[Resultado completo](reports/2026-11-16-qmp-build-result.md).
Uma cópia DT diagnóstica foi preparada e rechecado o layout, com revisão
limitada dos bootargs RAM-first; não é validação de todos os parâmetros herdados.
SHA-256 DT `212b80a051570874811ef504dcf4356cfd4226a262851dd84ed0c70089be8a09`.
[Escopo e testes](reports/2026-11-16-qmp-diagnostic-dt.md). Contagem histórica desta seção: 41 aprovações.

O projeto produziu um kernel candidato, initramfs BusyBox e DTB mínimo USB2,
além de um loader corrigido e ferramentas de investigação. **Não houve boot
validado do segundo kernel.** O caminho antigo de execução permanece bloqueado
sob CFI; nenhum teste de retorno simples comprova o handoff completo.

Os principais bloqueios são captura recuperável dos logs, protocolo de CPUs,
quiescência de DMA/SMMU/dispositivos e entrada arquitetural completa. O alvo
inicial não inclui discos montados nem uma instalação SteamOS.

## Últimos resultados no aparelho

Consulta única autorizada concluída: **13 descritores dinâmicos localizados**,
396 MiB (380 MiB baixos + 16 MiB altos). Uma inserção; módulo/sysfs/temporário
removidos e ausência reconferida no mesmo boot, CPUs `0-5` inalterados. Nenhuma
pausa de CPUs, leitura de PFNs/conteúdo físico ou aquisição de páginas. Não
repetir a consulta: a autorização de inserção única foi consumida.
[Endereços e limites](reports/2026-11-17-reserved-descriptor-result.md).

O boot coincide com a coleta RO DT/iomem/zonas e com o envio interrompido
anterior. Esse envio teve zero inserções; o caminho temporário antigo foi
confirmado ausente após reconexão. A transferência em blocos passou na retomada.
A nova captura pertence a outro boot em relação a PMSG/pageblocks históricos.
[Mapas](reports/2026-11-17-memory-map-device-result.md),
[auditoria](reports/2026-11-17-dynamic-reservation-audit.md) e
[falha de transporte histórica](reports/2026-11-17-reserved-descriptor-preparation.md).

Última amostra autorizada de pageblocks: 11 MOVABLE e 2 UNMOVABLE, todos na
zona DMA; callback de 2,604 µs e cleanup confirmado. O boot dessa amostra é
posterior às capturas PMSG/DT anteriores; não misturar as procedências.
[Resultado](reports/2026-11-16-pageblock-device-result.md). Nenhuma posse de
RAM ou segurança DMA foi demonstrada.

Teste autorizado de marcador PMSG em 2026-11-16: escrita única, marcador
único no ring lógico no offset 66.248, snapshot de 589.824 bytes íntegro,
boot ID consistente e remoção confirmada de módulo/temporários. **Aprovado
somente para emissão e captura no mesmo boot**, sem reset. Não valida WARM,
early-root ou callbacks finais. [Relatório](reports/2026-11-16-pmsg-same-boot.md).

Coleta inicial de 2026-11-16, anterior ao marcador no boot anterior: 589.824 bytes passaram com hashes
e boot ID conferidos, seguida de remoção confirmada do módulo. PMSG tem 712
bytes e cauda zerada. Magisk começou aos 69,49 s, antes do panicreporter
observado aos 80,46 s; uma execução anterior desse consumidor não foi excluída.
Portanto, early-root e retenção WARM continuam não validados. Consulte o
[relatório da sessão](reports/2026-11-16-continuity.md) e o
[próximo experimento proposto](NEXT-EXPERIMENT.md).

| Experimento | Resultado | Limite |
|---|---|---|
| Preflight RO do loader | insmod/rmmod 0 | Não executa shutdown ou salto |
| CPU1 | desligou/restaurou, `0-5` ao final | Não valida todos os CPUs |
| EFI | boot/runtime/reset indisponíveis | Bloqueia essa alternativa de reset |
| Snapshot ramoops | 589.824 bytes, hashes conferidos, unload 0 | Cópia inicial pode concorrer com escritores |
| Modo reset | COLD=0, panic=-1 | Snapshot não prova modo do reset anterior |
| Guard reversível | 0 → 1 → 0, cleanup confirmado | Não executa firmware |
| Pedido WARM | modo1/owned1 antes, ack ADB0 | Handler de firmware não observado |
| Captura após pedido WARM | marcador ausente; pmsg atual712 bytes, restante zerado | Houve resets completos adicionais do Singularity |

O usuário esclareceu que os resets intermediários foram automáticos durante
as tentativas de root. Na quinta tentativa o root voltou sem novo reset
forçado. Assim, a captura final atravessou uma sequência não isolada de boots.
**Não classificar esse caso como uma demonstração de que WARM perde RAM.**

## Decisão de continuidade

| Candidato separado | Estado atual | image_size |
|---|---|---|
| QMP | Compilado e checado, sem boot | 43,125 MiB |
| USB trim1 | Compilado e checado, sem boot | 39,125 MiB |
| USB trim2 | Image-only compilado e checado, sem boot | 35,9375 MiB |
| USB trim3 | Image-only compilado e checado, sem boot | 31,25 MiB |

O maior trecho MOVABLE da amostra histórica tem 24 MiB; os tipos não foram
revalidados no boot da nova coleta RO. Nenhum dos quatro cabe nesse trecho antigo;
reduzir só initramfs/DT não resolve. Nenhuma nova base foi selecionada ou
adquirida. [Geometria](reports/2026-11-16-placement-geometry.md),
[trim1](reports/2026-11-16-usb-trim-result.md) e
[trim2 concluído](reports/2026-11-17-usb-trim2-result.md).

**Direção de aquisição em avaliação:** APIs CMA padrão + buddy separadamente
para initrd/DT, sem varrer PFNs arbitrários. ARM64 não exige uma janela única
para os três artefatos; a anterior de 40 MiB era conservadora. O descritor do
pool padrão observado tem 32 MiB; trim3 atende ao teto com image_size de 31,25 MiB.
A margem de tamanho de 0,75 MiB não é folga CMA: o pedido arredondado ocupa
todos os 32 MiB nominais, sem capacidade nominal restante. Image/initrd/DT
somam pedidos de 36 MiB; a janela combinada ainda não cabe no pool.
Identidade runtime do ponteiro CMA padrão, disponibilidade e contrato de uma
alocação ainda não foram validados. Nenhuma chamada de alocação ou nova carga
de módulo foi feita nesta etapa; os candidatos anteriores permanecem intactos.
Não usar pools dedicados.
Meta de tamanho concluída: trim3 remove apenas BTF embutido, KALLSYMS_ALL e
KUnit, mantendo símbolos de funções/DWARF/pstore e proteções. Próximo marco:
revisar plano de identidade CMA padrão, ABI/lifetime e rollback, antes de
qualquer experimento separado e explicitamente autorizado. Layout separado
ainda não implementado no loader; nenhuma posse ou prontidão para boot.
[Método, orçamento e critérios de interrupção](reports/2026-11-17-stock-allocation-decision.md).
[Preparação trim3](reports/2026-11-17-usb-trim3-preparation.md).
[Resultado trim3](reports/2026-11-17-usb-trim3-result.md).

Plano de identidade CMA separado da aquisição e modelo host revisados:
comparar ponteiro padrão/priv antes do accessor de nome, rejeitar inconsistências,
devolver referência OF e não repetir tentativa. **42 testes host aprovados**;
na etapa do plano, nenhum módulo novo preparado/carregado ou identidade runtime confirmada.
[Escopo, gates e limpeza propostos](reports/2026-11-17-default-cma-identity-plan.md).

Consulta C e controlador backend-free implementados em `quest3/cma-identity-query/`:
**44 testes host aprovados**, incluindo corpos C reais com mocks e falhas de
transferência/inserção/limpeza simuladas. Controlador desarmado, sem hash de
binário aprovado ou transporte real. Essa foi a etapa do protótipo, anterior ao
build stock abaixo. [Protótipo](reports/2026-11-17-default-cma-identity-prototype.md).

Build stock ARM64 da consulta agora concluído em saída separada: .ko de
280.784 bytes, 23 versões/CRCs conferidos no ELF contra a tabela stock, imports
restritos e CFI/SCS/Full LTO/MODVERSIONS mantidos. **45 testes host aprovados**.
Artefatos/logs arquivados; controlador continua desarmado, sem transporte live,
nenhuma carga no Quest. Próximo marco: revisão de fonte/transporte/reconciliação
antes de qualquer nova autorização específica; não autoriza alocação.
[Build e limites](reports/2026-11-17-default-cma-identity-build.md).

Revisão de transporte/recuperação concluída com correções: timeout/resposta sem
fence, interrupção ou falha do journal agora bloqueiam **todos** os comandos
posteriores, pois insmod/dd podem continuar ativos. Guardas remotas de boot/token
acrescentadas; **46 testes host aprovados**, sem alterar o .ko ou operar no Quest.
Uso live continua bloqueado por recibo remoto/quiescência, lease/isolamento de
caminhos e adaptador ADB/su ainda não revisados/implementados.
[Achados e runbook](reports/2026-11-17-cma-transport-recovery-review.md).

Referência filesystem de recibos/lease implementada somente no host: claims e
receipts imutáveis, pinagem de diretório/inode da trava, bloqueio após crash sem
recibo e fd herdável sem LOCK_UN prematuro. **47 testes host aprovados**. Não é
supervisor remoto, não despacha ações e não foi integrada ao controlador; gates
de Android/filesystem/SELinux, caminhos/lease canônicos, reconciliação e ADB
continuam abertos. Nenhuma operação no Quest ou alteração do .ko.
[Referência e limites](reports/2026-11-17-cma-receipt-lease-reference.md).

Núcleo supervisor C agora testado somente com fixtures do host: fork/exec por
FD, wait/reap, captura bounded separada, recibo persistido antes da resposta e
lease herdada após SIGKILL. Default desarmado; **48 testes host aprovados**.
Recibo v2 não migra o ledger v1 automaticamente. Ainda sem build Android/Bionic,
dispatcher stock, bootstrap/catálogo nativos ou integração com controlador/ADB.
Nenhuma operação no Quest; .ko/Image preservados.
[Resultado e gates](reports/2026-11-17-cma-native-supervisor-host.md).

NDK oficial r30/30.0.16248370 baixado com autorização e preparado somente em
`.work/android-ndk-r30/`: tamanho/SHA-1 publicados e CRCs conferidos, SHA-256
local registrado. Clang 21 inicia no host; kernel/módulo seguem na toolchain
anterior. **48 testes host reconferidos**, sem instalação global ou Quest.
Toolchain preparada antes do build abaixo; download não prova ABI/runtime nem
autoriza implantação.
[Preparação e procedência](reports/2026-11-17-android-ndk-r30-preparation.md).

Primeiro build ARM64/Bionic API28 concluído e checado offline: main desarmado
de 5.608 bytes e linkcheck de 23.576 bytes, ambos com main write/retorno 77 no
disassembly. PIE/NX/RELRO/NOW, dependências libc.so/libdl.so e metadados API/NDK
conferidos. Full LTO/CFI trap userspace registrados; SCS userspace não presumido
sem runtime revisado. **49 testes host aprovados**; nenhum Android ELF executado
ou enviado ao Quest, .ko/Image e proteções kernel preservados. Restam dispatcher,
bootstrap/catálogo v2, recuperação, ABI/runtime e autorização específica.
[Artefatos e limites](reports/2026-11-17-cma-native-android-build.md).

Bootstrap/catálogo v2 revisados: v2 não registra ordem/predecessor, então não
serve sozinho para admissão sequencial. Observador host explícito implementado
com pins/boot/lease e manifesto esperado, validando recibos C reais de fixtures
sem migrar o ledger v1 ou descongelar o controlador. **50 testes host aprovados**;
replay/cleanup/retomada/durabilidade do ACK continuam não autorizados/demonstrados.
Nenhum C/ELF Android, kernel ou módulo alterado. Bootstrap/writer nativos e
envelope encadeado seguem gates abertos, sem operação no Quest.
[Contrato proposto e testes](reports/2026-11-17-cma-v2-catalog-bootstrap-review.md).

Rascunho v3 não executável modelado: seis papéis tipados, ordinal/nonces,
compromisso do receipt anterior com outcome e checkpoint local explícito.
**51 testes host aprovados**, incluindo cauda reescrita/recalculada: hashes
provam consistência, não autenticidade/história; partes não ancoradas nunca
liberam execução. Vetores sintéticos preservados. Nenhum writer/bootstrap
nativo, integração, migração ou operação no Quest; binários C/Android/kernel
anteriores preservados. [Rascunho e limites](reports/2026-11-17-cma-v3-chain-draft.md).

Bootstrap nativo separado, padrão desarmado, validado apenas com fixtures de host:
raiz fixa exclusiva sob pai previamente ancorado, lease e publicação de metadados
sem sobrescrita; falhas/estado parcial permanecem barreiras, sem takeover.
**52 grupos host aprovados, zero falhas/ignorados**, incluindo substituições,
concorrência, SIGKILL e perda de resposta. Observador separado apenas propõe pins;
não importa, ativa, admite, migra ou retoma. Sem build Android deste componente,
integração com controlador ou operação no Quest. Bootstrap de produção/ACK local
durável, writer e dispatcher seguem pendentes.
[Resultado e limites](reports/2026-11-17-cma-native-bootstrap-host.md).

Build Android separado do bootstrap concluído offline: API28/Bionic/NDK r30,
main desarmado mínimo de 5.608 bytes e núcleo retido de 17.688 bytes, ambos com
main limitado a write/retorno 77. Flags Full LTO/CFI, stack protector, FORTIFY,
x18 reservado e PIE/RELRO/NOW verificadas em evidência local; SCS userspace não
habilitado e enforcement/runtime não testados. **53 grupos host aprovados**,
zero falhas/ignorados. Nenhum ELF Android executado/transferido, nenhum pin
importado, writer ativado ou operação no Quest. Artefatos anteriores preservados.
Próximo gate: ACK/importação local durável, ainda sem admissão.
[Build e limites](reports/2026-11-17-cma-bootstrap-android-build.md).

Referência de journal local de ACK/importação implementada apenas para fixtures:
intent/ACK/import publicados separadamente sob raiz/lease fixadas, com checkpoint
devolvido ao mesmo writer vivo. Falha congela a instância; reinício só permite
observação, sem reconstruir checkpoint ou writer a partir de arquivos completos.
**54 grupos host aprovados**, zero falhas/ignorados, incluindo fsync incerto,
SIGKILL e corrupção antes do retorno. Completion é uma fixture, não validação de
transporte; flags reais de importação/admissão/ativação continuam falsas. Sem
rebuild Android, integração ou operação no Quest; artefatos anteriores preservados.
[ACK local e gates restantes](reports/2026-11-17-cma-bootstrap-local-ack.md).

Contrato puro de completion do bootstrap acrescentado: frame nonce/status
existente + resposta/recibo exatos + wait/streams/boot fornecidos, sem afirmar
autenticidade das observações. Comparação de reinício exige compromisso de
checkpoint externo anterior; bytes coincidentes não recuperam writer nem
habilitam importação/retomada. **55 grupos host aprovados**, zero falhas/ignorados,
incluindo cauda reescrita/recalculada. Nenhum publisher de âncora externa,
integração de journal/controlador, rebuild Android ou operação no Quest.
Mecanismo de âncora e origem confiável de completion continuam pendentes.
[Contrato e limites](reports/2026-11-17-cma-bootstrap-completion-contract.md).

Direção de âncora escolhida pelo usuário: witness separado, começando apenas por
testes locais sem instalar serviço. Referência host SQLite FULL/Ed25519 criada:
vínculo único por pending em cada base, verificação com chave pública anterior,
declarações distintas de publicação/observação e reopen somente read-only.
**56 grupos host aprovados**, zero falhas/ignorados. Teste explícito mostra que
duas bases com a mesma chave podem assinar histórias conflitantes: isolamento,
rollback/não-equivocação, cliente/política e deployment continuam pendentes.
Sem chave operacional, rede/serviço, integração, rebuild Android ou operação no
Quest; nenhuma assinatura habilita importação/admissão ou retomada.
[Witness e limites](reports/2026-11-17-cma-bootstrap-witness-host.md).

Auditoria read-only de declarações do witness acrescentada: comparação com digest
anterior do caller e artefato portátil com duas assinaturas para bindings distintos
do mesmo pending. **57 grupos host aprovados**, zero falhas/ignorados. Detecta
somente conflitos apresentados; testes preservam limites de fork oculto, âncora
autoselecionada e duplicatas que não contam como votos. Nenhum resultado permite
retomada/importação ou prova causa/ordem/ausência global de rollback. Witness e
controlador anteriores preservados, sem integração, serviço/rede, rebuild Android
ou operação no Quest. Proteção preventiva e política do cliente seguem pendentes.
[Auditoria e limites](reports/2026-11-17-cma-witness-signed-conflict-audit.md).

Wrapper host de identidade/política do cliente do witness acrescentado: chaves
prévias distintas, scope exato de digests/ações, challenge/submission/response
assinados e claim de nonce em memória antes da delegação. **58 grupos aprovados**,
zero falhas/ignorados. Rejeições congelam gate e witness; testes de trace confirmam
ausência de consultas delegadas para mensagens inválidas/repetidas. Reutilização
forçada de sessão de teste recria challenge: não há prova de anti-replay durável
ou rollback. API raw do witness continua sendo fixture, não endpoint autenticado.
Sem provisionamento, serviço/rede, integração, rebuild Android ou operação no
Quest; origem da política, isolamento e proteção preventiva continuam pendentes.
[Política do cliente e limites](reports/2026-11-17-cma-witness-client-policy-host.md).

Usuário escolheu log e monitor independente como próxima direção, apenas offline.
Modelo bounded implementado: três chaves distintas, heads Merkle assinados,
checkpoint anterior do caller e varredura completa de até 128 entries. Rejeita
redução/reescrita/reordenação, prefixo incompleto e bindings conflitantes anexados.
**59 grupos host aprovados**, zero falhas/ignorados. Baseline antigo ainda permite
ao signer-modelo produzir outra branch: persistência/frescor da âncora atual e
isolamento operacional continuam pendentes. Sem store de log/monitor, serviço,
rede, integração, rebuild Android ou operação no Quest; artefatos preservados.
[Log/monitor e limites](reports/2026-11-17-cma-witness-log-monitor-host.md).

Store host do monitor implementado: validação unsigned separada, intenção com
predecessor único confirmada em SQLite FULL/fsync antes da assinatura e publicação
atômica de checkpoint/head por CAS. Falhas congelam; raiz existente bloqueia novo
writer e reinício é somente inspeção read-only, sem recuperar ACK ou importar
âncora. **60 grupos aprovados**, zero falhas/ignorados; teste específico passou
também no filesystem do projeto. Snapshot antigo no mesmo inode é detectado
apenas se o caller preservar âncora externa mais recente: independência/frescor
e recuperação operacional seguem pendentes. Modelo log/monitor foi refatorado
sem alterar bytes assinados; fonte anterior arquivado. Sem deployment, rede,
integração, rebuild Android ou operação no Quest.
[Store e limites](reports/2026-11-17-cma-monitor-anchor-store-host.md).

Planejamento offline fora da janela fixa: nove intervalos com geometria para
40 MiB, incluindo bancos acima de 4 GiB. A exclusão explícita dos 13 intervalos
dinâmicos localizados não altera esses nove intervalos; todos já estavam fora
deles. Isso não demonstra disponibilidade: nenhum tipo de pageblock novo foi
medido, base escolhida ou página adquirida. Não ampliar sondagem com pausa de
CPUs sem plano e autorização próprios.
[Resultado e limites](reports/2026-11-17-memory-survey-planning.md).

Revisão offline de lifetime: mem_buf usa remoção de subseções sem passar
pelas notificações normais de offline. Módulos relevantes aparecem na captura
anterior, sem prova de que estejam removendo uma janela de interesse. Leitor
CPU, callback iomem ou notifier não substituem exclusão de hotplug de memória.
Contrato de lifetime para varredura permanece aberto; não ampliar stop_machine
ou carregar nova sonda com base apenas nas bases CMA agora conhecidas.
[Fonte, exports e modelo host](reports/2026-11-17-memory-lifetime-review.md).

Rastreio posterior delimitou remoção mem_buf normal aos SGLs aceitos/importados
e adicionados por S1, com rollback só do prefixo bem-sucedido. Nova importação
conflitante com recurso BUSY é recusada, mas isso não prova histórico/procedência
dos nove intervalos. DT supplier bloqueia ALLOC, não elimina RETRIEVE no fonte.
Helpers de unmap não revalidam por si mesmos a propriedade de cada região;
endereços dos SGLs ativos não estão inventariados. Nenhuma janela declarada
imune, nova sonda carregada ou operação no Quest nesta revisão.
[Regiões alcançáveis e limites](reports/2026-11-17-mem-buf-removal-ranges.md).

Alternativas de procedência revisadas offline: removable só reflete config;
DMA-BUF sysfs fornece nome/tamanho, não SGL, e sua criação é assíncrona. Os
nove intervalos cruzam 60 seções de 128 MiB: 56 totalmente cobertas por System
RAM e quatro com buracos no snapshot. Nenhuma classe prova imunidade vendor,
procedência contínua de boot ou lifetime dos PFNs. Não foi preparada nova
sonda nem feita operação no Quest.
[Limites das interfaces e cobertura](reports/2026-11-17-memory-provenance-limits.md).

Coletor de DT/iomem/zonas preparado e testado com ADB simulado, com boot
antes/depois, hashes, recusa de dados incompletos e saída privada sem sobrescrita.
Primeira execução no Quest aprovada, sem carregar módulos ou pausar CPUs.
[Contrato e uso](reports/2026-11-17-memory-map-collector.md).

Bloqueios independentes continuam abertos:

- **Posse da RAM:** a janela contém páginas ocupadas e tipos mistos. A API
  vendor alloc_contig_range tem cinco argumentos e exige contrato próprio;
  não houve aquisição/migração. A sonda original sem sincronização continua
  recusando hotplug. [Memória](reports/2026-11-16-memory-ownership.md).
- **Handoff CFI/CPUs/DMA:** 18 referências privadas do fonte não estão nos
  exports stock fornecidos. Callbacks tipados não resolvem contexto atômico,
  CPU_OFF ou quiescência. [Auditoria](reports/2026-11-16-handoff-api-audit.md).
- **AOP/QMP:** provedores agora embutidos nos novos candidatos, mas handshake
  e estado herdado Anorak não foram validados. Patches Pro são referência,
  não uma configuração transplantável. [Dependências](reports/2026-11-16-qmp-dependencies.md).
- **Logs:** PMSG no mesmo boot passou, mas captura anterior aos consumidores
  e callbacks finais continua pendente. O dmesg preservado começa tarde demais
  para excluir execução anterior de panicreporter.
  [Linha do tempo](reports/2026-11-16-startup-timeline.md).

O histórico das preparações, recusas e etapas intermediárias permanece nos
relatórios vinculados no README, sem sobrepor estados antigos ao resumo atual.

Suspender repetições do mesmo teste e manter Android/root estáveis. O próximo
método precisa ler o conteúdo antes das novas tentativas de root ou usar um
transporte independente. Nenhum early-root hook foi demonstrado com esta
instalação do Singularity; BOOT_COMPLETED não garante ordem anterior ao init
que inicia panicreporter. UART ou outro canal externo exige validação real de
hardware/pinagem; não há configuração pronta comprovada neste repositório.

Não executar `execute=1`, ensaios físicos ou um novo reset WARM como se os
bloqueios já estivessem resolvidos. Não há necessidade de flash de partições
para examinar os resultados publicados.

## Artefatos de referência

- Image: `cee2f89539dba8ec4c87351ccef350ba2a614dfd2b47778588c95c580e96234d`.
- Initramfs USB: `32dce3695e184dbea3738c0750d76ae211fe19b564cc23e83375cad04d19e34e`.
- DT USB gerado no computador: `ef9a2557908b0904e5b96683ca52696a0bc080fccd9ddea4fda73e4126ce7367`.
- DT diagnóstico: `9604a24fad0e33c78fb2f78ecc133f5e4774350947dc2c9dd2ada07495c76e6d`.
- Módulo local do usuário com layout: `9b69276030ffe896751cf7c1d6f5d2ddde7ebdfd5bfe37e52efe86585959f6f6`.
- Snapshot RO: `403c9161a293cb6ce322c3ec0412268026c77e21b68f741c9436025f01993e2d`.
- Guard: `1b1e60ac53583e7c70058b839758348756d1a7ac739a993482104f9c17e6c829`.

Os hashes são identificadores de artefatos específicos. Compilações locais
podem variar por metadados/toolchain; um release string igual não comprova
equivalência binária. Os manifestos calculados nesta publicação descrevem os
arquivos efetivamente incluídos, sem substituir a história dos testes.
