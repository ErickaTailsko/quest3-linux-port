# Checklist atual do porte Quest 3

Legenda: `[x]` concluído no escopo indicado; `[ ]` pendente. Compilação,
simulação, teste em hardware e validação de boot são evidências diferentes.

## Progresso global — atualização de 2026-11-19

**Estimativa: ~40% do objetivo final (faixa subjetiva de 35–45%).** Não é
medição formal, proporção de caixas marcadas, estimativa de tempo restante ou
indicação de prontidão para boot. A parte restante concentra os maiores riscos.

- Preparação offline avançada: candidatos kernel/initramfs/DT, ferramentas,
  revisão de fontes/ABI e modelos de layout, fases e cobertura preservados.
- Última suíte: **69 grupos host aprovados, zero falhas/ignorados**. Isso não
  comprova posse de RAM, lifetime, publicação física de cache ou handoff no alvo.
- Nenhum destino adquirido, staging direto implementado ou boot alternativo
  demonstrado. Loader preservado; controlador e monitor operacional bloqueados.
- Image trim3 continua solicitando **32 MiB CMA**, toda a capacidade nominal
  considerada, sem disponibilidade ou folga comprovada.

### Prioridades restantes

- [x] Definir contrato e critérios de aceitação/rejeição do eventual helper leaf
  direto (ABI/CFI/SCS/BTI/PAC/ranges), sem helper implementado ou aprovado.
- [x] Implementar subconjunto read-only de ELF/BTI/registradores/PAC/ranges e
  fixtures negativas; 68 grupos, resultado global só PENDING/REJECT.
- [x] Revisar/endurecer limites do parser e auditar vínculo local de callers/
  imports: 72 CRCs consistentes, dependência qcom-scm explícita; não prova build/ABI.
- [x] Implementar checagens reutilizáveis de conteúdo/versões/provedor/namespace/
  dependências e política explícita, com negativos; 69 grupos, sem aprovação runtime.
- [x] Especificar pacote de evidências e plano de build offline isolado (B0–B5),
  com diretórios novos e proteções preservadas; nenhum helper/build executado.
- [ ] Revisar proposta de fontes/caller inerte, retenção Full LTO e contexto de
  linha/retorno antes de implementar/construir candidato isolado; sem loader/Quest.
  Revisão textual: `docs/reports/2026-11-23-cache-leaf-b0-source-review.md`.
  Leitor sanitizado público encontrado; B0 segue PENDING por ABI/geometria,
  retenção não comprovada, erratas e contexto.
  Revisão adicional: `docs/reports/2026-11-23-cache-leaf-b0-hotplug-abi-review.md`.
  Draft separado: `docs/reports/2026-11-23-cache-leaf-explicit-geometry-abi-draft.md`.
  Três argumentos propostos; passo S não prova envelope de efeitos G. Não adotado.
  Revisão: `docs/reports/2026-11-25-cache-leaf-preshutdown-envelope-review.md`.
  APIs públicas de hotplug confirmadas; contexto/ordem de locks e G/operação
  seguem pendentes, sem candidato/build.
- [ ] Validar identidade, capacidade/impacto e lifetime do CMA padrão e adquirir/
  reter destinos reais Image/initrd/DT, com pares de liberação e handles originais.
- [ ] Implementar e validar staging, zero-fill, integridade/readback, mappings,
  exclusão de writers/DMA e publicação até PoC após a última escrita.
- [ ] Integrar alocações retornadas ao loader e validar entrada ARM64 compatível
  com as proteções; se escolhida a hipótese direta, criar transição sem cópia.
- [ ] Fechar shutdown de CPUs/dispositivos, DMA/SMMU, watchdog e QMP/RPMh,
  limites de abort, transporte/supervisão, âncora independente e logs recuperáveis.
- [ ] Validar progressivamente no Quest e demonstrar BusyBox/initramfs, USB ECM,
  IP/shell e recuperação de falhas no kernel novo.

**Próximo gate offline:** revisar proposta de fontes/caller inerte e retenção
Full LTO antes de implementar/construir candidato; lifetime real segue pendente.
Qualquer operação no aparelho exige nova autorização específica; autorizações
consumidas não podem ser reutilizadas.
Nenhum item pendente acima foi autorizado ou executado por esta atualização.

## Fontes, build e proteções

- [x] Identificar kernel do aparelho: `5.10.246-gd7102a837402`, ARM64.
- [x] Preparar fonte pública e Clang Android 14.0.7 r450784e.
- [x] Construir kernel/módulos com CFI estrito, SCS, Full LTO e MODVERSIONS.
- [x] Comparar 15.919 CRCs exportados com o Module.symvers fornecido.
- [x] Resolver geração BTF com pahole adaptado para a ambiguidade CFI.
- [x] Preservar `x18` e LR no frame de 96 bytes do retorno ARM64.
- [x] Bloquear caminhos de símbolos privados incompatíveis com CFI.
- [ ] Implementar handoff completo usando interfaces compatíveis com CFI.
- [ ] Demonstrar equivalência completa ao kernel binário do fabricante;
  o hash interno do aparelho não é o commit público disponível.

## SCM e plataforma

- [x] Substituir ABI SCM legado por chamadas exportadas `qcom_scm_*`.
- [x] Obter endereços/formatos do DT e validar o esquema de seis CPUs.
- [x] Manter escrita core-hang bloqueada no esquema legado do Quest real.
- [x] Tratar falhas e restauração de USB, watchdog e GPU nos caminhos previstos.
- [x] Testar falhas parciais, referências e propagação de erros em host.
- [x] Executar preflight RO independente no aparelho; inserir/remover passou.
- [ ] Validar preparação completa de todos os dispositivos para o salto.
- [ ] Estabelecer contrato de DMA/SMMU, RPMh/AOP, GPU e periféricos.
- [ ] Validar watchdog de aplicação/seguro no fluxo completo; o comando seguro
  de desativação não oferece uma operação inversa equivalente.

## Primeiro alvo em RAM

- [x] BusyBox 1.36.1 estático ARM64, fontes/config e licenças preservadas.
- [x] Initramfs CPIO verificável; `/init` sem montagens de discos.
- [x] Fluxo USB ECM: alvo `10.42.0.2/24`, host `10.42.0.1/24`.
- [x] Kernel candidato com 33 provedores/imports relevantes embutidos.
- [x] DTB USB2 peripheral/high-speed: sete alterações semânticas permitidas.
- [x] Preservar ambos os PHYs e as reservas de memória.
- [x] Evitar roundtrip textual do dtc antigo que alterava uma propriedade.
- [x] Validar janela `[0x90000000,0x93400000)` no iomem capturado.
- [x] Corrigir entrada pelo `text_offset`: offset zero entra em `0x90000000`.
- [x] Ajustar `/chosen/linux,initrd-start/end` em cópia do DTB.
- [x] Preparar bootargs de diagnóstico com `rdinit=/init`.
- [ ] Reservar/assegurar destino contra alocação e DMA do kernel antigo;
  ausência de sobreposição no iomem não significa posse da RAM.
- [ ] Iniciar Image/initramfs/DTB no Quest.
- [ ] Validar enumeração USB, IP, shell e funcionamento dos drivers no alvo.

## CPUs e reinício

- [x] Teste individual CPU1: desligamento e restauração, máscara final `0-5`.
- [x] Modelar múltiplos CPUs e rollback com falhas simuladas.
- [ ] Resolver concorrência e desligamento de todos os CPUs secundários.
- [x] Confirmar EFI runtime/reset indisponível no teste do aparelho.
- [x] Compilar observadores tipados de reboot/syscore/restart, sem uso ativo.
- [x] Ler modo atual: COLD (`0`), panic não especificado (`-1`).
- [x] Validar em hardware ciclo COLD → WARM → COLD sem reiniciar.
- [x] Solicitar um reinício com política WARM armada e receber ack do ADB.
- [ ] Comprovar qual handler/rota de firmware concluiu esse reset.

## Logs persistentes — bloqueio atual

- [x] Analisar console/PMSG, init e crash reporter.
- [x] Comprovar no binário uma rota de descarte/purge de logs sem panic.
- [x] Verificar logcatd; sua configuração não prova execução e não contém
  a combinação explícita `logcat -L -c` nas regras recebidas.
- [x] Procurar descritores pstore abertos: nenhum encontrado na captura.
- [x] Identificar que os FDs de console na saúde são do modo charger.
- [x] Capturar RAM ramoops por módulo RO validado no aparelho e SHA256.
- [x] Testar marcador PMSG com preenchimento e referência verificada.
- [x] Confirmar ausência do marcador e cauda zerada após teste COLD.
- [x] Criar referência nova e solicitar teste WARM.
- [x] Registrar que o Singularity causou reinícios completos adicionais antes
  da coleta; root só voltou na quinta tentativa.
- [ ] Isolar retenção WARM: o último resultado é **inconclusivo** por esses
  reinícios intermediários; não prova falha nem sucesso exclusivo do WARM.
- [ ] Obter captura anterior às tentativas de root ou transporte externo.
- [ ] Validar registro dos callbacks finais antes de ensaios de transição.

## Publicação e continuidade

- [x] Registrar sessão de 2026-11-16 em relatório revisado, sem novos logs privados.
- [x] Revalidar snapshot RO no aparelho, hashes, boot consistente e cleanup.
- [x] Executar 23 verificações host sem falhas ou testes ignorados nesta sessão.
- [x] Autorizar e validar marcador PMSG no mesmo boot, sem reset (2026-11-16).
- [x] Automatizar análise offline da linha do tempo; suíte atual com 24 aprovações.
- [x] Revisar HOW_TO_PORT do Quest Pro e revalidar DT/layout com a captura atual.
- [x] Auditar dependências mailbox AOP/QMP e disponibilidade no initramfs mínimo Quest 3.
- [x] Compilar candidato separado com provedores AOP/QMP embutidos (Image e 236 módulos).
- [ ] Validar handshake e estado herdado Anorak em hardware, após os pré-requisitos de captura/handoff.
- [x] Preparar fontes/toolchain fixadas, pahole e configuração QMP separada.
- [x] Testar corpo real qmp_open em host, com sucessos e falhas simuladas.
- [x] Revisar normalização da config e preparar verificador de artefatos QMP; 25 testes host aprovados.
- [x] Aplicar verificador ao novo Image completo e registrar hashes/layout.
- [x] Preparar DT diagnóstico QMP, revisar política RAM-first dos bootargs e revalidar layout.
- [x] Reproduzir inventário das 18 referências privadas e cruzar exports stock/contextos de restart.
- [x] Capturar metadados RO da janela RAM e revisar assinatura vendor de alloc_contig_range.
- [x] Identificar migratetype dos 13 pageblocks em uma amostra sincronizada: 11 MOVABLE, 2 UNMOVABLE.
- [ ] Demonstrar posse de um destino elegível, sem confundir com segurança DMA.
- [x] Preparar protótipo RO com testes host e recusa de hotplug sem proteção de lifetime.
- [ ] Demonstrar proteção de lifetime compatível com APIs stock antes de carga da sonda pageblock.
- [x] Preparar alternativa stop_machine desarmada, compilar com config/CRCs stock fornecidos e auditar imports.
- [x] Autorizar e avaliar uma amostra stop_machine no aparelho, com coleta e remoção confirmadas.
- [x] Calcular geometria: trechos MOVABLE de 12/8/24 MiB não comportam Image de 43,125 MiB.
- [ ] Definir estratégia adquirível de posicionamento antes de generalizar o layout do loader.
- [x] Medir baseline e preparar redução usb-trim1 sem perder provedores explícitos/hardening conferido.
- [x] Concluir build usb-trim1 e verificar artefatos/geometria: 39,125 MiB, redução insuficiente para 24 MiB.
- [x] Revisar cortes incrementais de rede/filesystems e preparar perfil usb-trim2 separado.
- [x] Concluir build usb-trim2 e verificar Image: 35,9375 MiB, ainda acima de 24 MiB; sem posse demonstrada.
- [x] Planejar geometria fora da janela fixa com DT/iomem históricos: nove intervalos, sem escolher base ou adquirir páginas; 33 testes host aprovados.
- [x] Preparar coletor RO de DT/iomem/zonas com boot antes/depois, hashes e testes ADB simulados; suíte com 34 aprovações, sem captura nova no Quest.
- [x] Reconectar Quest ao ADB e obter capturas novas correspondentes, somente leitura: dez leituras aprovadas com hashes/boot conferidos, sem módulos/pausa de CPUs.
- [x] Localizar os 13 descritores dinâmicos no boot da coleta, com consulta única autorizada; 396 MiB identificados, sem prova de RAM disponível.
- [x] Inventariar os 13 pedidos CMA, consumidores e restrições; auditar interfaces/logs no mesmo boot e confirmar export tipado de consulta, sem carga de módulo.
- [x] Autorizar/preparar consulta única dos 13 descritores: módulo com vinte CRCs stock, proteções e testes; suíte com 36 aprovações.
- [x] Restabelecer ADB no mesmo boot e confirmar ausência do temporário da falha de envio, que teve zero inserções.
- [x] Executar a única consulta autorizada (uma inserção) e confirmar remoção de módulo/sysfs/temporário, com checagem posterior e CPUs inalterados.
- [x] Revisar lifetime/exports e caminho vendor de remoção de subseções; adicionar modelo host de concorrência (37 testes), sem nova operação no aparelho.
- [ ] Demonstrar contrato de lifetime para a janela exata incluindo caminhos vendor antes de ampliar sondagem; leitor CPU/notifier/iomem não bastam.
- [x] Rastrear origem RM/SGL, capability supplier, pareamento e conflitos BUSY do mem_buf; testar corpos C revisados com mocks (38 testes host), sem nova operação no Quest.
- [ ] Estabelecer importações ativas/procedência contínua da janela exata; captura System RAM e localização dos pools CMA não provam imunidade a remoção.
- [x] Revisar removable/DMA-BUF sysfs e cobertura de seções: 60 cruzadas, 56 integrais e quatro com buracos no snapshot; nenhuma prova de imunidade, 39 testes host aprovados.
- [x] Comparar rotas de aquisição stock: exports CMA/buddy, limites e alocações separadas; modelo de posse/rollback e 41 testes host, sem chamar alocadores no Quest.
- [x] Produzir candidato dentro do teto nominal de 32 MiB: trim3 verificado com image_size de 31,25 MiB e proteções/requisitos preservados; pedido arredondado ainda ocupa todos os 32 MiB, sem prova de disponibilidade.
- [x] Concluir build Image trim3 separado, arquivar artefatos/hashes e medir redução de 4,6875 MiB desde trim2; 41 testes host aprovados, sem boot ou alocação.
- [x] Validar layout host de três blocos retornados de fixtures: Image/CMA padrão, initrd/DT buddy, bounds/slots/janela ARM64/DT e chosen-only rewrite; 61 grupos aprovados, sem aquisição, base real escolhida ou alteração do loader.
- [ ] Revisar validador C e integração desarmada de faixas retornadas com staging, descritores e exclusão de fontes/scratch; geometria host não comprova posse/lifetime ou autoriza alocação/handoff.
- [x] Implementar núcleo C aritmético separado e consulta de interseção com os três slots completos; UBSan, saídas preservadas em erro e 2.000 casos diferenciais, com 62 grupos host aprovados, sem incluir o header no loader.
- [ ] Revisar representação/lifetime e aliases de fontes/descritores/código/page tables/scratch e plano de staging; máscara sem interseção não comprova aquisição ou validade de páginas.
- [x] Modelar recursos de staging/snapshots e descritores 255-entry apenas no host, com aliases/zero-fill/chain corruption e 63 grupos aprovados; retenção de metadados não comprova handles vivos, sem integração/handoff.
- [x] Comparar offline relocação (~68,63 MiB) versus direto hipotético (~36,02 MiB, buffer 4 KiB); 64 grupos aprovados, mesma Image CMA 32 MiB, sem posse/escrita/handoff ou pico medido.
- [x] Detalhar contrato documental de handles/mappings/lifetime, streaming/cache e falhas da hipótese direta; distinguir readback de clean até PoC, sem implementação/aprovação runtime ou novo grupo de testes.
- [x] Modelar traços host das fases/falhas do contrato direto, recusando escrita antecipada, selagem incompleta, mutação após clean e comandos após incerteza; 65 grupos aprovados, sem writer/integração ou prova de recursos reais.
- [x] Confrontar offline contrato direto com fontes/ABI stock e mapping/cache: pares CMA/buddy disponíveis, PoC helpers sem export e flush_dcache_page apenas flag; sem adaptador/build/operação no Quest, permanecem 65 grupos.
- [x] Revisar offline opções de cache e fronteiras do fluxo: observação/freezer/USB, watchdog seguro sem inversa e shutdown global distintos; rollback legado não comprovado, 65 grupos e nenhum helper/adapter aprovado.
- [x] Modelar cobertura por ranges/última escrita no host: bytes/linhas dirty, PoC/I-cache e fronteiras independentes, com oráculo seeded e 66 grupos; sem helper/assembly/writer/loader ou admissão runtime.
- [x] Compor vínculo host de layout, fases e cobertura sob recursos/ranges exatos: writes de payload derivados, seal/final-clean coerentes e 67 grupos; trim3 sintético com buffer 64 KiB, sem admissão runtime (4 KiB completo excede o limite desta composição).
- [x] Revisar offline evidências necessárias de lifetime/ABI/CFI: lookup sem pin, risco de lock order e três calls diretos em leaf histórico com BTI/x18 preservado; nenhuma claim promovida, sem build/port live, 67 grupos.
- [x] Definir contrato leaf v1 e critérios L01–L14, com PAC explícito em todos os retornos, separação ABI/cache/lifetime e vetores/controles negativos especificados; sem helper/verificador novo, 67 grupos.
- [x] Implementar verificador estático read-only parcial do contrato leaf: parser ELF bounded, BTI/registradores/PAC CFG e ranges uint64, com controles negativos e 68 grupos; sem aprovação global, helper ou execução de bytes.
- [x] Endurecer limites de nomes/queries do parser e auditar hashes/callers/imports do ELF histórico: 72 versões/CRCs compatíveis e dependência qcom-scm observada; 68 grupos, proveniência/ABI completa permanecem PENDING.
- [x] Automatizar checks host de conteúdo/versões/CRCs/providers/namespaces/dependências e política explícita, com negativos e substituição coerente ainda PENDING; 69 grupos, sem prova de build/CFI/lifetime ou autorização.
- [x] Especificar pacote completo e plano B0–B5 de build offline isolado, sem criar candidato ou pastas de build, rodar Kbuild ou integrar loader; permanecem 69 grupos.
- [ ] Revisar proposta de fontes/caller inerte, retenção sob Full LTO e contexto de linhas/PAC/retorno antes de implementar/construir candidato; sem autorizar carga ou execução.
- [ ] Validar contrato direto com handles/ABI/plataforma reais e revisar transição sem cópia antes de qualquer implementação/ativação runtime; exige escopo e autorização novos no aparelho.
- [ ] Validar identidade do pool padrão, lifetime/ABI e autorização de eventual experimento de aquisição/liberação; não usar pools dedicados nem habilitar handoff.
- [x] Revisar plano de consulta de identidade CMA sem aquisição, separado do teste de alocação; modelo fake de ordem/cleanup/uso único, 42 testes host aprovados, sem execução no Quest.
- [x] Implementar fonte da consulta de identidade e controlador desarmado sem transporte real; testes de corpos C e falhas simuladas, 44 testes host aprovados, sem módulo ARM64 construído ou carga no Quest.
- [x] Construir consulta de identidade contra stock no host e verificar imports/CRCs/proteções: .ko ARM64 de 280.784 bytes, 23 versões/CRCs conferidos no ELF, 45 testes host aprovados; controlador continua desarmado.
- [x] Revisar transporte/recuperação: corrigir cleanup prematuro após timeout, exigir fence por comando e bloquear após incerteza/interrupção/falha de journal; guards remotos, 46 testes host aprovados, sem dispositivo.
- [ ] Revisar/implementar recibo remoto de conclusão, quiescência, lease/isolamento de caminhos e adaptador ADB/su antes de qualquer habilitação live ou nova autorização específica; sem aquisição implícita.
- [x] Implementar referência host de recibos/lease persistentes: publicação exclusiva/fsync, pinagem, barreira de claim após crash e fd herdável; 47 testes aprovados, sem dispatcher ou integração live.
- [ ] Implementar/revisar supervisor Android e wait/reap, raiz/lease canônicas e validação de filesystem/SELinux antes de integrar recibos/observação ao controlador; receipt recuperado não autoriza cleanup.
- [x] Preparar núcleo supervisor C com default desarmado e fixtures host: wait/reap, streams bounded, recibo antes da resposta, lease herdada/sinais/falhas; 48 testes aprovados, sem build Android ou operação no Quest.
- [ ] Concluir gate Android/Bionic além do build desarmado já verificado: ABI/runtime, dispatcher, bootstrap/catálogo nativos e schema v2 antes de qualquer integração live.
- [x] Baixar NDK r30 oficial com autorização, verificar tamanho/SHA-1/CRCs e registrar SHA-256; preparar em .work sem instalação global, 48 testes host reconferidos e sem operação no Quest.
- [x] Construir main ARM64/Bionic API28 desarmado e variante de linkcheck do núcleo: ELF/imports/versões/PIE/NX/RELRO/NOW e flags conferidos, 49 testes host aprovados; sem execução Android ou alteração de proteções kernel.
- [ ] Revisar dispatcher stock, bootstrap/catálogo v2, observação de recuperação e ABI/runtime antes de integrar o helper; build desarmado não autoriza envio, cleanup ou alocação.
- [x] Revisar bootstrap/catálogo v2 e implementar observação explícita no host: pins/boot/lease, recibos de fixtures C e rejeição de inconsistências; 50 testes aprovados, sem admissão/migração/replay/cleanup ou dispositivo.
- [ ] Revisar envelope de sequência/predecessor/ações tipadas e implementar bootstrap/writer nativos; recibos v2 sem ordem não autorizam transações ou retomada.
- [x] Modelar rascunho v3 não executável com papéis/argumentos tipados, links por receipt/outcome, checkpoints locais e vetores sintéticos; 51 testes host aprovados, incluindo reescrita de cauda não ancorada sem alegação de autenticidade.
- [ ] Revisar protocolo de produção/bootstrapping nativo e claim-before-effect sob lease, sem tratar hash de autorização ou modelo v3 como permissão de executar.
- [x] Implementar referência nativa de bootstrap somente de metadados, padrão desarmado, com raiz exclusiva/pai ancorado e observador sem importação; 52 grupos host aprovados, incluindo falhas, substituições, concorrência e resposta perdida.
- [ ] Validar build Android separado do bootstrap e revisar pai/boot/autorização reais, ACK/importação duráveis e ativação; referência host não concede admissão ou operação no Quest.
- [x] Compilar bootstrap separado ARM64/Bionic API28 em variantes mínima/núcleo retido, ambas desarmadas; verificar ELF/flags/IR/imports/main offline e preservar evidências, com 53 grupos host aprovados, sem execução Android.
- [ ] Modelar ACK local durável/importação explícita de pins sob contexto e journal fixados, sem ativação implícita ou retomada após falha incerta.
- [x] Implementar referência host de intent/ACK/importação explícita somente de pins de fixtures, checkpoint no mesmo writer vivo e observação sem recuperação após falha/reinício; 54 grupos aprovados, sem admissão real.
- [ ] Revisar completion/contexto reais e âncora independente de reconciliação do ACK; integrar importação de produção somente após gate explícito, sem ativar writer pela leitura de bytes completos.
- [x] Modelar completion com framing nonce/status existente, reply/receipt exatos, contexto wait/streams/boot fornecido e comparação por checkpoint externo anterior; 55 grupos host aprovados, sem autenticação, publisher externo ou retomada.
- [ ] Escolher/revisar mecanismo independente de âncora e origem confiável das observações antes de implementar publisher/reconciliação operacional; outro arquivo autodeclarado não resolve ACK incerto.
- [x] Registrar escolha do usuário por witness separado e testar referência local SQLite FULL/Ed25519: vínculo único por base, chave anterior, publicação vs observação, falhas/SIGKILL e reopen read-only; 56 grupos aprovados, sem deployment/admissão.
- [ ] Revisar isolamento, autenticação/política do cliente e proteção contra rollback/não-equivocação do witness; duas bases com a mesma chave ainda podem assinar histórias conflitantes.
- [x] Implementar auditoria read-only com âncora de binding anterior e evidência portátil de dois bindings assinados conflitantes; 57 grupos aprovados, com limites de forks ocultos/âncora autoselecionada e sem votos por duplicatas, prevenção ou retomada.
- [x] Testar wrapper host de política do cliente: chaves distintas, scope exato publish/observe, mensagens assinadas e nonce reclamado antes da delegação; 58 grupos aprovados, sem serviço autenticado de produção, origem de política ou anti-replay durável.
- [x] Registrar escolha do usuário por log + monitor independente e testar modelo bounded de heads Merkle, âncora anterior e varredura completa de bindings; 59 grupos aprovados, sem persistência/deployment ou garantia contra baseline antigo.
- [ ] Especificar armazenamento/recuperação da âncora atual do monitor e domínio independente de confiança; assinatura com chave distinta não impede rollback de seu estado.
- [x] Implementar store host one-lifetime com intenção durável antes da assinatura, predecessor único, CAS de head e inspeção read-only sem recuperação; 60 grupos aprovados e teste adicional no filesystem do projeto, sem alegar resistência a rollback conjunto de banco/âncora.
- [ ] Definir autoridade/armazenamento independente da âncora mais recente e recuperação operacional, impedindo bypass do store/assinador; SQLite e pins locais não fecham esse gate.
- [x] Organizar fontes atuais, revisões, scripts, relatórios e diagnósticos.
- [x] Documentar resultados negativos/inconclusivos e bloqueios reais.
- [x] Preservar pacotes entregues e checksums; inventariar exclusões de build.
- [ ] Validar handoff, recuperação e primeiro boot antes de qualquer release
  operacional. A publicação de pesquisa não encerra essas pendências.
