# USB trim3 — Image de 31,25 MiB verificado, sem boot

**Build Image concluído com retorno zero e verificador aprovado.** A meta de
image_size ≤ 32 MiB foi atingida sem alterar os candidatos anteriores. Esta
etapa foi somente no host: nenhuma alocação, carga de módulo ou operação no Quest.

## Medidas e identidade

| Medida | Resultado |
|---|---|
| Release | `5.10.246-gd7102a837402-q3-usb-trim3` |
| image_size do cabeçalho ARM64 | 32.768.000 bytes / 31,25 MiB |
| Arquivo Image | 31.152.640 bytes |
| Redução efetiva desde trim2 | 4.915.200 bytes / 4,6875 MiB |
| Redução efetiva desde QMP | 12.451.840 bytes / 11,875 MiB |
| Margem de tamanho até 32 MiB | 786.432 bytes / 0,75 MiB |

Image SHA-256:
`215c0baf386deb0dc7f8f584dae0ce8bd757b8fb4055482c9942c1fe4c99c5f4`.
Config SHA-256:
`8ded98e4406cb925afd6bcc2a606d36ba31fa1cd9173259a1c3b02ea3d141206`.

Fonte `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`; Android Clang 14.0.7
r450784e, revisão `425c8149f17c8d9914bf690b4d5abe45a13fb993`.
A [preparação](2026-11-17-usb-trim3-preparation.md) registra a configuração,
o patch host extract-cert.c e HOSTCFLAGS=-DOPENSSL_NO_ENGINE. Foi um build
incremental em saída separada, semeada por cópia do trim2, não um build frio
nem uma demonstração de reprodutibilidade binária. Não foi feito build completo
de módulos.

## Cortes e preservações

Somente DEBUG_INFO_BTF, KALLSYMS_ALL e KUNIT passaram de y para n na config
normalizada. BTF embutida caiu de 3.683.354 para zero bytes; o intervalo entre
kallsyms_names e kallsyms_markers caiu de 1.900.632 para 925.112 bytes. Esses
valores são componentes medidos, não uma decomposição exata de toda a redução.

Perdem-se BTF/CO-RE do alvo, nomes extras de símbolos de dados e framework
KUnit embutido. Permanecem kallsyms de funções, frame pointers e DWARF no host
(.debug_info de 115.141.928 bytes), pstore/ramoops/console/PMSG, drivers e
provedores USB/QMP requeridos, CFI estrito, SCS, Full LTO e MODVERSIONS.
SELinux, seccomp, usercopy, stack protector, RWX estrito e KASLR continuam
checados. Flags de compilação dos provedores foram verificadas; isso não
constitui prova de comportamento runtime ou de toda a cadeia de dependências.

O log preserva duas mensagens Git sobre `dbc2bc83a~..HEAD`, indisponível no
histórico raso. Make terminou com retorno zero; o emissor exato dessas mensagens
não foi identificado. Elas não foram ocultadas nem tratadas como build limpo.

## Tamanho não é disponibilidade

**A margem de 0,75 MiB não é capacidade CMA sobrando.** Com arredondamento
revisado de 2 MiB, a solicitação do Image continua sendo 33.554.432 bytes:
todos os 32 MiB nominais do descritor observado. Capacidade nominal fora dessa
solicitação: **zero**. Não se demonstrou que o pool esteja livre, seja o padrão
runtime ou possa entregar essa alocação.

Initrd e DT em slots separados de 2 MiB levam o total planejado a 36 MiB.
A janela combinada também permanece em 36 MiB e não cabe no pool nominal
de 32 MiB nem no antigo trecho MOVABLE de 24 MiB. O loader de endereço fixo
ainda não implementa o layout separado com endereços retornados por alocadores.
Nenhuma base foi selecionada, nenhum alocador foi chamado e nenhuma página
foi adquirida.

Antes de qualquer experimento, revisar identidade do ponteiro CMA padrão
contra o priv do descritor linux,cma, ABI stock, disponibilidade, lifetime,
limites de impacto e rollback. A consulta anterior foi consumida; nova carga
de módulo ou teste de alocação exige plano e autorização separados. Não usar
pools dedicados nem ampliar sondagens com pausa de CPUs automaticamente.
Logs recuperáveis, handoff compatível com CFI, CPUs secundárias, DMA/SMMU,
watchdog e QMP herdado continuam gates independentes; não houve boot alternativo.

## Evidências preservadas

Em `quest3/usb-trim/`: `trim3-verification.json`, `trim3-geometry.json`,
`trim3-allocation-assessment.json` e `trim3-comparison.json`.
Image, vmlinux DWARF, config, mapas, comandos dos provedores e log estão
arquivados com hashes conferidos em `private-diagnostics/usb-trim3-artifacts/`.
Resultado do job: `private-diagnostics/usb-trim3-build-01/result.json`.

A suíte host após acrescentar regressões da geometria real trim3 passou com
**41 aprovações, zero falhas e zero testes ignorados**. As regressões confirmam
31,25→32 MiB, ausência de capacidade nominal fora da solicitação arredondada,
total de 36 MiB e ausência de afirmações de posse/prontidão.
