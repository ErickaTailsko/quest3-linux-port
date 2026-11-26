# USB trim3 — build separado para o orçamento de 32 MiB

**Registro histórico de preparação; build agora concluído e verificado.**
Resultado: image_size de 31,25 MiB; veja o [relatório final](2026-11-17-usb-trim3-result.md).
As referências a tamanho pendente abaixo descrevem a etapa de preparação. Não houve
operação ADB, nova carga de módulo, aquisição de RAM ou tentativa de boot.

## Objetivo e cortes revisados

A [decisão de aquisição stock](2026-11-17-stock-allocation-decision.md) definiu
a rota candidata: Image no CMA padrão, initrd e DT em alocações separadas.
Trim2 tem image_size=35,9375 MiB, excedendo o teto nominal de 32 MiB em
3,9375 MiB. Não se presume que esse pool esteja livre ou seja adquirível.

Novo fragmento: `quest3/usb-trim/trim3.fragment`. A normalização do Kconfig
removeu somente três opções antes habilitadas:

| Opção | Mudança e custo |
|---|---|
| DEBUG_INFO_BTF | Remove typeinfo BTF embutida; perde-se esse suporte de introspecção/CO-RE no alvo |
| KALLSYMS_ALL | Remove nomes extras de dados; kallsyms de funções e backtraces permanecem habilitados |
| KUNIT | Remove o framework de testes embutido; os testes KUnit listados já estavam desabilitados |

As outras 13 linhas do diff removem opções de testes que já eram n e deixaram
de ser configuráveis após desligar KUnit. Não houve corte de novos provedores
de hardware para forçar dependências, nem desligamento de CFI/SCS/LTO.

Mantidos: DEBUG_INFO/DWARF4 para análise no host, FRAME_POINTER, KALLSYMS,
pstore/ramoops/console/PMSG, MODVERSIONS, SELinux, seccomp, usercopy, stack
protector, RWX estrito, KASLR e os provedores explícitos USB/QMP/plataforma.
DWARF não é confundido com bytes embutidos no Image; sua remoção não foi usada
como uma suposta economia de RAM.

## Preparação e origem

- Fonte: `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`.
- Clang Android 14.0.7 r450784e; mesmo helper tools/q3make.
- Única alteração no fonte kernel continua sendo o patch host revisado
  scripts/extract-cert.c, usado com HOSTCFLAGS=-DOPENSSL_NO_ENGINE.
- Baseline config SHA-256:
  `5bdae0670303ed5fa7dbe1bce6bf145279abba5c6fee0e1c63f3584cceb927c1`.
- Config trim3 SHA-256:
  `8ded98e4406cb925afd6bcc2a606d36ba31fa1cd9173259a1c3b02ea3d141206`.
- Release solicitado: `5.10.246-gd7102a837402-q3-usb-trim3`.

Config pública em `quest3/configs/usb-trim3.config`; diff e relatório em
`quest3/usb-trim/trim3-config.diff` e `trim3-preparation.json`.
olddefconfig terminou com retorno zero; manteve dois avisos do lexer gerado
sobre variáveis não usadas, preservados no log local.

## Saída e verificação do build

Preparação em `.work/usb-trim3-config/`. Build em
`.work/usb-trim3-build-out/`, iniciado com -j2 e alvo Image. Para evitar trabalho
desnecessário, a nova saída foi semeada com uma cópia dos objetos trim2; make
reavalia comandos/dependências/config e relinka o novo candidato. A saída
original não foi alterada. Não se afirma build frio ou reprodutibilidade binária.

Log: `.work/usb-trim3-build-out/trim3-build-image.log`.
Intenção e resultado automático: `private-diagnostics/usb-trim3-build-01/`.
O job faz a verificação ao terminar; não há repetição automática de build
nem tentativa de usar o Image caso a verificação falhe.

O verificador agora reconhece o release trim3, recusa BTF/KALLSYMS_ALL/KUnit
reativados, exige os diagnósticos/proteções mantidos e rejeita image_size
acima de **32 MiB**. Também recusa BTF ainda presente no System.map. O campo
image_entry está explicitamente marcado como referência do layout antigo,
não como base nova escolhida. Os perfis anteriores não perderam suas verificações.

A regressão inclui teto exato de 32 MiB, rejeição de um byte além, ausência de
diagnósticos/proteções e reativação dos cortes. Suíte: **41 aprovações, zero
falhas ou testes ignorados**. QMP, trim1 e trim2 existentes continuam passando
no verificador atualizado; os binários anteriores foram preservados.

## Limites

Somente o cabeçalho do Image efetivamente produzido confirmará o tamanho.
Mesmo atingir o teto não prova folga no CMA padrão, ABI, identidade runtime,
disponibilidade, posse, segurança DMA ou suporte do loader ao layout separado.
O build não autoriza alocação, esgotar o pool padrão, usar pools dedicados,
carregar módulos no stock ou iniciar handoff. Logs/CPUs/QMP herdado e protocolo
arquitetural continuam gates independentes.
