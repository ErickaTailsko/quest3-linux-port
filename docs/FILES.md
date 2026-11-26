# Navegação e classificação

## Atuais

`quest3/module` contém loader.c, transition.S, quest3-layout.h,
quest3-scm.c/h e quest3-platform.c/h. marker_read/usb_log são ferramentas
separadas; o hook USB privado permanece bloqueado sob CFI.

`ram-first`, `usb-minimal` e `ram-kernel-plan` contêm fontes/configurações,
geradores e validações do alvo. `layout-review` contém a correção da entrada,
os patches entregues e cópias DT de cada fase.

`ramoops-snapshot`, `reset-mode-info` e `warm-reset-guard` contêm os módulos
de observação e os controladores recentes, inclusive upload em blocos, PMSG,
checagem antes/depois e pedido único de reboot. **Ter o arquivo disponível
não é indicação para executar um novo teste no hardware.**

## Históricos

Diretórios `*-fix`, `baseline-module-source`, `local-complete`,
`native-kexec-package`, `cfi-transition-audit`, `handoff-order-audit`,
`restart-backend-design`, `restart-readiness`, `early-capture` e os probes
documentam hipóteses e revisões. Alguns programas foram propositalmente
bloqueados com EOPNOTSUPP; outros são ensaios anteriores. Consulte STATUS.

`quest3/CHECKLIST.md`, `build-info.json` e logs antigos descrevem o momento
em que foram criados. Por exemplo, campos device_accessed=false se referem
ao build cloud, não negam os testes feitos posteriormente pelo usuário.

## Dados e binários

Os arquivos originais enviados foram copiados para `diagnostics/uploads`,
mantendo o agrupamento original para diferenciar nomes repetidos. Incluem
PDF, textos colados, fontes, config, symvers, DTB, logs, biblioteca fornecida,
listagem de FDs e arquivos compactados com snapshots antes/depois.

O Image canônico está em `quest3/ram-first-kernel/arch/arm64/boot/Image`.
A entrada `ram-first-candidate/Image` aponta para ele. Módulos pequenos e
initramfs também estão no Git; pacotes completos entregues estão na release.
`manifests/release-assets-local.json` fornece tamanho e SHA256 dos pacotes.

Nomes antigos com `.private` foram preservados como nomes históricos. Eles
foram incluídos na publicação pública mediante autorização para os brutos;
o nome do arquivo não representa um controle de acesso no GitHub.

## Inventários

- `manifests/files.json`: caminhos, tamanhos e hashes do material publicado.
- `manifests/SHA256SUMS`: verificação direta dos arquivos.
- `manifests/workspace-exclusions.json`: árvores e intermediários omitidos.
- `manifests/host-tests.json`: execução da suíte no snapshot publicado.
- `manifests/release-assets-local.json`: pacotes binários/históricos.
- `manifests/upstreams.json`: revisões externas usadas.

Os manifestos não incluem a si próprios em um ciclo de hashes. O commit Git
e o checksum do asset completam a identificação do snapshot publicado.
