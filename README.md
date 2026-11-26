# Eris — pesquisa de porte Linux para Meta Quest 3

Fontes, ferramentas, binários, diagnósticos e registro técnico do trabalho com
`quest-kexec` no Quest 3 **Eureka/Anorak**, usando os projetos Quest 2 SteamOS e
quest-kexec como referências.

**Estado atual: o kernel alternativo ainda não foi iniciado no Quest 3.**
Esta publicação contém fontes e documentação selecionadas, não o workspace
completo. Capturas brutas, binários e evidências privadas não são enviados;
parte dos testes depende de inputs locais. Veja [escopo](docs/COMPLETENESS.md)
e [publicação](docs/PUBLISHING.md).

O salto permanece bloqueado sob CFI. A captura confiável dos logs finais do
kernel também está pendente. Compilação ou carregamento de um módulo de
diagnóstico não comprovam que o porte está pronto para boot.

O aparelho usado tem bootloader travado e root obtido pelo Singularity.
O primeiro alvo é pequeno: **BusyBox estático em initramfs, sem montagens de
discos, USB Ethernet e logs recuperáveis**. Não foi instalado um sistema
SteamOS completo nem uma imagem de boot alternativa.

## Começar pela documentação

- [Continuidade de 2026-11-16](docs/reports/2026-11-16-continuity.md): coleta atual, correções e limites.
- [Teste PMSG no mesmo boot](docs/reports/2026-11-16-pmsg-same-boot.md): aprovado, sem reset.
- [Linha do tempo reproduzível](docs/reports/2026-11-16-startup-timeline.md): root, consumidores e lacunas da captura.
- [Comparação com Quest Pro](docs/reports/2026-11-16-quest-pro-reference.md): limites de portabilidade e nova revisão do layout.
- [Auditoria AOP/QMP](docs/reports/2026-11-16-qmp-dependencies.md): provedores ausentes do alvo mínimo e proposta de build.
- [Novo candidato QMP compilado](docs/reports/2026-11-16-qmp-build-result.md): artefatos/layout conferidos, boot não testado.
- [DT diagnóstico QMP](docs/reports/2026-11-16-qmp-diagnostic-dt.md): bootargs RAM-first e layout revisados offline.
- [Auditoria do handoff CFI](docs/reports/2026-11-16-handoff-api-audit.md): exports stock, contextos e contrato de memória pendente.
- [Posse de RAM](docs/reports/2026-11-16-memory-ownership.md): metadados atuais, ABI vendor e limites da reserva contígua.
- [Sonda pageblock](docs/reports/2026-11-16-pageblock-probe-design.md): protótipo host, bloqueado por contrato de lifetime pendente.
- [Alternativa stop_machine](docs/reports/2026-11-16-stop-machine-proposal.md): proposta histórica, riscos e preparação do módulo.
- [Amostra pageblock no aparelho](docs/reports/2026-11-16-pageblock-device-result.md): 11 blocos MOVABLE e 2 UNMOVABLE, cleanup confirmado.
- [Geometria de posicionamento](docs/reports/2026-11-16-placement-geometry.md): Image não cabe nos trechos observados; plano relativo sem nova base.
- [Redução experimental USB](docs/reports/2026-11-16-usb-trim-result.md): build aprovado, Image de 39,125 MiB ainda não cabe no trecho observado.
- [Segunda redução USB](docs/reports/2026-11-17-usb-trim2-result.md): build aprovado, Image de 35,9375 MiB; destino ainda não adquirido.
- [Geometria fora da janela fixa](docs/reports/2026-11-17-memory-survey-planning.md): planejamento histórico de nove intervalos; nenhuma base escolhida.
- [Coletor de mapas RO](docs/reports/2026-11-17-memory-map-collector.md): testes host e primeira coleta real aprovados.
- [Novos mapas no Quest](docs/reports/2026-11-17-memory-map-device-result.md): boot consistente na coleta, geometria reproduzida; posse ainda pendente.
- [Auditoria das reservas dinâmicas](docs/reports/2026-11-17-dynamic-reservation-audit.md): inventário dos pedidos CMA e caminho tipado para consulta.
- [Preparação da consulta](docs/reports/2026-11-17-reserved-descriptor-preparation.md): build checado e falha histórica de transporte, resolvida na retomada.
- [Descritores localizados](docs/reports/2026-11-17-reserved-descriptor-result.md): 13 bases/tamanhos, uma inserção e cleanup confirmados; sem pausa de CPUs ou posse de RAM.
- [Lifetime antes de ampliar sondagem](docs/reports/2026-11-17-memory-lifetime-review.md): caminho vendor exige revisão adicional; nenhuma nova operação no aparelho.
- [Quais regiões mem_buf remove](docs/reports/2026-11-17-mem-buf-removal-ranges.md): SGLs importados, conflitos BUSY e limites do modo supplier; nenhuma janela declarada imune.
- [Procedência e cobertura de seções](docs/reports/2026-11-17-memory-provenance-limits.md): limites de sysfs e contagem offline, sem inferir imunidade ou preparar nova sonda.
- [Decisão de aquisição stock](docs/reports/2026-11-17-stock-allocation-decision.md): rota CMA padrão + buddy em estudo; teto de Image de 32 MiB, trim2 ainda não cabe; nenhuma alocação realizada.
- [Terceira redução USB concluída](docs/reports/2026-11-17-usb-trim3-result.md): Image de 31,25 MiB verificado, proteções mantidas; pedido CMA arredondado ainda de 32 MiB, sem alocação ou boot.
- [Plano de identidade CMA](docs/reports/2026-11-17-default-cma-identity-plan.md): revisão e modelo host, separado da aquisição; 42 testes aprovados, sem nova carga de módulo.
- [Protótipo da consulta CMA](docs/reports/2026-11-17-default-cma-identity-prototype.md): fonte e controlador desarmado testados com mocks; 44 testes aprovados, sem transporte real ou build de módulo ARM64.
- [Build stock da consulta CMA](docs/reports/2026-11-17-default-cma-identity-build.md): módulo ARM64 verificado, 23 versões/CRCs conferidos no ELF e 45 testes aprovados; implantação continua desabilitada, sem carga no Quest.
- [Revisão de transporte e recuperação](docs/reports/2026-11-17-cma-transport-recovery-review.md): corrigido cleanup prematuro após timeout; 46 testes aprovados. Uso live segue bloqueado, sem operação no Quest.
- [Referência de recibo persistente e lease](docs/reports/2026-11-17-cma-receipt-lease-reference.md): filesystem/locks/crash testados no host, 47 testes aprovados; sem supervisor remoto, dispatcher ou integração live.
- [Núcleo supervisor C no host](docs/reports/2026-11-17-cma-native-supervisor-host.md): wait/reap e recibo antes da resposta, 48 testes aprovados; default desarmado, sem build Android/Bionic ou operação no Quest.
- [NDK r30 preparado](docs/reports/2026-11-17-android-ndk-r30-preparation.md): download oficial autorizado e verificado, restrito a .work; pronto para preparar o build Bionic desarmado, sem implantação.
- [Build ARM64/Bionic desarmado](docs/reports/2026-11-17-cma-native-android-build.md): dois artefatos API28 verificados offline, 49 testes aprovados; nenhum executável Android iniciado ou enviado ao Quest.
- [Bootstrap/catálogo v2 e observação](docs/reports/2026-11-17-cma-v2-catalog-bootstrap-review.md): observador host explícito e 50 testes aprovados; recibos sem sequência não autorizam admissão, replay ou cleanup, sem operação no Quest.
- [Rascunho v3 encadeado](docs/reports/2026-11-17-cma-v3-chain-draft.md): modelo não executável, papéis tipados/checkpoints e vetores sintéticos; 51 testes aprovados, sem autenticidade ou permissão inferidas de hashes.
- [Bootstrap nativo de metadados](docs/reports/2026-11-17-cma-native-bootstrap-host.md): referência separada e desarmada, raiz exclusiva e recuperação somente observacional; 52 grupos host aprovados, sem importação de pins ou ativação.
- [Build Android do bootstrap](docs/reports/2026-11-17-cma-bootstrap-android-build.md): dois ELFs API28 desarmados verificados offline; 53 grupos host aprovados, sem execução ou transferência ao Quest.
- [ACK local do bootstrap](docs/reports/2026-11-17-cma-bootstrap-local-ack.md): journal de fixtures com intent/ACK/import separados e congelamento após falha; 54 grupos aprovados, sem admissão ou recuperação automática de checkpoint.
- [Contrato de completion do bootstrap](docs/reports/2026-11-17-cma-bootstrap-completion-contract.md): framing/contexto e comparação por âncora externa em modelo puro; 55 grupos host aprovados, sem publisher ou retomada operacional.
- [Witness do bootstrap — referência host](docs/reports/2026-11-17-cma-bootstrap-witness-host.md): direção separada escolhida pelo usuário, SQLite/Ed25519 e 56 grupos aprovados; sem serviço instalado, proteção contra rollback ou admissão no controlador.
- [Auditoria de conflitos assinados](docs/reports/2026-11-17-cma-witness-signed-conflict-audit.md): âncora anterior e evidência portátil para forks apresentados; 57 grupos host aprovados, sem prevenção de rollback ou retomada.
- [Política de cliente do witness](docs/reports/2026-11-17-cma-witness-client-policy-host.md): wrapper de fixtures com scope e mensagens assinadas; 58 grupos host aprovados, sem serviço instalado, anti-replay durável ou admissão.
- [Log e monitor independente](docs/reports/2026-11-17-cma-witness-log-monitor-host.md): direção escolhida pelo usuário, modelo Merkle/prefixo completo e 59 grupos aprovados; armazenamento da âncora atual e proteção operacional continuam pendentes.
- [Store host da âncora do monitor](docs/reports/2026-11-17-cma-monitor-anchor-store-host.md): intenção durável antes de assinar, publicação CAS e 60 grupos aprovados; reinício somente observacional, sem proteção contra rollback conjunto de banco/âncora.
- [Layout offline por alocações retornadas](docs/reports/2026-11-18-returned-allocation-layout-host.md): geometria separada Image/initrd/DT, janela ARM64 e chosen-only rewrite; 61 grupos host aprovados, com endereços fictícios, sem alocação ou alteração do loader.
- [Núcleo C do layout separado](docs/reports/2026-11-18-returned-layout-c-core-host.md): aritmética e máscaras de interseção dos três destinos; 2.000 casos diferenciais/UBSan e 62 grupos aprovados, sem integração com loader ou prova de posse.
- [Staging e descritores — modelo host](docs/reports/2026-11-18-relocation-staging-plan-host.md): snapshots/aliases e cadeia de descritores, com 63 grupos aprovados; ~68,63 MiB contabilizados no cenário de relocação, sem aquisição, lifetime comprovado ou handoff.
- [Relocação versus direto — comparação offline](docs/reports/2026-11-18-staging-comparison-host.md): ~68,63 versus ~36,02 MiB condicionais, mesma Image CMA de 32 MiB; 64 grupos aprovados, sem writer, aquisição ou ativação runtime.
- [Contrato do staging direto — revisão documental](docs/reports/2026-11-18-direct-staging-contract-review.md): handles/lifetime, streaming, selagem versus PoC e matriz de falhas; nenhum gate runtime liberado.
- [Traços do staging direto — somente host](docs/reports/2026-11-18-direct-staging-traces-host.md): progresso bounded, fases e falhas terminais, 65 grupos aprovados; claims não comprovam posse/cache/execução, sem writer ou integração.
- [Staging direto — fontes/ABI stock](docs/reports/2026-11-18-direct-staging-stock-abi-review.md): contratos CMA/buddy e lacuna de exports PoC revisados offline; flush_dcache_page não substitui clean, sem adaptador ou gate runtime liberado.
- [Publicação de cache e fronteiras](docs/reports/2026-11-18-cache-publication-boundary-review.md): observador/USB e mutações sem inversa antecedem shutdown global; nenhum helper aprovado ou operação no Quest.
- [Cobertura de cache por ranges — host](docs/reports/2026-11-18-cache-publication-ranges-host.md): última escrita invalida claims de PoC/I-cache, 66 grupos aprovados; nenhum helper, publicação física ou admissão runtime.
- [Vínculo layout/fases/cobertura — host](docs/reports/2026-11-18-staging-binding-host.md): timeline única e recursos exatos, 67 grupos; cenário trim3 sintético com buffer 64 KiB, sem writer, helper ou admissão runtime.
- [Lifetime e ABI/CFI — evidências offline](docs/reports/2026-11-18-lifetime-helper-abi-evidence-review.md): descritores não pinam páginas, lock order exige revisão e calls diretos antigos não aprovam novo helper ou entrada.
- [Contrato de aceitação do helper leaf](docs/reports/2026-11-18-cache-leaf-acceptance-contract.md): critérios L01–L14 e controles negativos definidos; ABI/PAC, cache e lifetime separados, sem helper ou verificador implementado.
- [Verificador estático leaf — subconjunto host](docs/reports/2026-11-19-cache-leaf-static-verifier-host.md): ELF/BTI/registradores/PAC/ranges read-only e controles negativos, 68 grupos; resultado global sempre PENDING/REJECT, sem helper ou admissão runtime.
- [Limites do parser e evidência de callers/imports](docs/reports/2026-11-19-cache-leaf-parser-caller-evidence-review.md): custo de nomes/queries endurecido e 72 CRCs históricos conferidos; dependência qcom-scm explícita, sem prova completa de build/ABI ou helper aprovado.
- [Imports e política explícita — host](docs/reports/2026-11-19-cache-leaf-import-policy-host.md): checks reutilizáveis de versões/provedores/namespaces e conteúdo, 69 grupos; consistência nunca aprova build, helper ou execução.
- [Plano de build isolado do futuro leaf](docs/reports/2026-11-19-cache-leaf-isolated-build-plan.md): pacote de evidências e gates B0–B5 definidos, sem fontes de candidato, build ou operação no Quest.
- [Continuidade experimental](docs/NEXT-EXPERIMENT.md): protocolo executado e próximo bloqueio.
- [Publicação no GitHub](docs/PUBLISHING.md): revisão, Git local e evidências privadas.
- [Checklist atual](CHECKLIST.md): concluído, testado no aparelho e pendente.
- [Estado e conclusões](docs/STATUS.md): interpretação dos testes e limitações.
- [Histórico técnico](docs/HISTORY.md): etapas, correções e experimentos.
- [Arquitetura e bloqueios](docs/ARCHITECTURE.md).
- [Compilação e testes locais](docs/BUILD.md).
- [Guia de navegação dos arquivos](docs/FILES.md).
- [Experimentos de retenção](docs/LOG-RETENTION.md).
- [Operação e continuidade](docs/OPERATIONS.md).
- [Pacotes e checksums](docs/ARTIFACTS.md).
- [Origem e licenças](docs/PROVENANCE.md).
- [Limites desta publicação](docs/COMPLETENESS.md).

## Conteúdo

| Caminho | Conteúdo |
|---|---|
| `quest3/module/` | Fontes atuais do loader, transição ARM64, SCM e plataforma |
| `quest3/ram-first/` | BusyBox, fonte original, configuração e geradores CPIO |
| `quest3/usb-minimal/` | Transformação binária do DTB, init USB ECM e testes |
| `quest3/ram-first-kernel/` | Image candidato e metadados; sem árvore de build completa |
| `quest3/layout-review/` | Verificação da janela de RAM, cabeçalho Image e `/chosen` |
| `quest3/ramoops-snapshot/` | Captura RO, transferência em blocos e comparação PMSG |
| `quest3/warm-reset-guard/` | Política WARM opt-in, reversão e controlador de teste |
| `quest3/*probe*/`, `quest3/*audit*/` | Ensaios, auditorias e modelos históricos |
| `diagnostics/uploads/` | Arquivos originais recebidos, inclusive capturas brutas |
| `manifests/` | Inventário, hashes, resultados e índice dos artefatos |
| `tools/` | Helpers portáveis para build e testes sem aparelho |

Os [pacotes binários e históricos estão na release](https://github.com/ErickaTailsko/eris/releases/tag/v0.1.0-research).
São artefatos de pesquisa, **não uma release de boot validada**. O pacote
`native-kexec-experimental` é uma alternativa histórica com divergências de
configuração, não o alvo mínimo atualmente selecionado.

## Verificação sem aparelho

```sh
python3 tools/verify-manifest.py
python3 tools/run-host-checks.py
```

Os testes acima usam simulações e compilação nativa de trechos C; não carregam
módulos nem solicitam reinícios. Os scripts de operação no aparelho são
separados e devem ser lidos com o estado atual antes de qualquer execução.
Em particular, não execute `execute=1`, testes físicos ou novos resets WARM
como se fossem a instalação do porte.

Os relatórios históricos em `quest3/` foram preservados. Alguns registram
pendências já resolvidas em uma etapa posterior. **Este README, o checklist e
`docs/STATUS.md` prevalecem como resumo atual.** Não há inicialização automática
de quest-kexec adicionada por este repositório.

Diagnósticos brutos foram incluídos mediante autorização expressa para este
repositório público. Credenciais não fazem parte da publicação.
