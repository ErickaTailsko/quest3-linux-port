# Resultado do build QMP — 2026-11-16

**Compilação de Image e módulos concluída com retorno zero.** Verificações de
artefatos e layout passaram. **Não houve boot nem teste do candidato no Quest.**
Este resultado atualiza o estado pendente do relatório de preparação, cujo
histórico de falhas e retomadas foi preservado.

## Identificação e resultado

| Item | Valor |
|---|---|
| Release | `5.10.246-gd7102a837402-q3-ram-first-qmp` |
| Image | 43.565.568 bytes |
| SHA-256 Image | `b1cca22c48f2a22e67229cc99b9bcd0778f019ad759130d142e6887a476e7e5b` |
| SHA-256 config | `14be9f34ae437272b94ab884f373b385ac8e09e6bb2ab2297c9ae86f662075e4` |
| Fonte | `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f` |
| Toolchain | Android Clang 14.0.7 r450784e, revisão `425c8149f17c8d9914bf690b4d5abe45a13fb993` |
| Build | dois jobs; Full LTO, BTF com pahole adaptado |
| Módulos gerados | 236 arquivos `.ko` |
| Diferença QMP na config normalizada | MSM_QMP e QCOM_AOSS_QMP: m → y |

O candidato antigo foi conferido e permanece com seu hash original. O novo
Image é uma alternativa experimental separada, não uma substituição validada.
Os módulos novos pertencem ao kernel alvo novo; não devem ser carregados no
Android stock apenas por terem sido compilados.

## Correção host e avisos

Única alteração da fonte: patch host `tools/patches/extract-cert-no-engine.patch`,
com `HOSTCFLAGS=-DOPENSSL_NO_ENGINE`. Extração PEM e assinatura com chave em
arquivo passaram por teste host. PKCS#11 ENGINE é recusado explicitamente.
CFI/SCS/LTO do alvo não foram desabilitados.

O build final contém avisos de qualificador const em modpost e frames de pilha
maiores que 2.048 bytes em funções de câmera e EVA. Não foram corrigidos nem
ocultados; não se deve chamar o build de livre de avisos. O registro de preparação
preserva também avisos Kconfig e a tentativa inválida com HOST_EXTRACFLAGS.

## Checagens efetivamente realizadas

- Configuração, release e cabeçalho ARM64 do Image; entrada por offset zero.
- MSM_QMP/AOSS em modules.builtin; IPCC e GICv3 habilitados como built-in.
- Flags registradas de CFI, SCS, LTO e x18 nos comandos dos provedores QMP.
- Símbolos QMP presentes no System.map, vmlinux com cabeçalho ELF64 ARM64 e
  Module.symvers produzido. Não houve auditoria completa de cada CRC/símbolo.
- Layout com initramfs USB2 e DT/iomem da captura atual: Image termina em
  `0x92b20000`; initrd `[0x93000000,0x9309145d)`;
  DTB `[0x93200000,0x932aaa3c)`. Chosen initrd confere.
- Comparações de reservas/layout não demonstram posse da RAM ou proteção DMA.

Metadados públicos: `quest3/qmp-audit/candidate-verification.json`,
`candidate-layout.json` e `quest3/configs/ram-first-qmp.config`.
Build completo em `.work/qmp-candidate-build-out/`. Cópia local do Image,
configuração, mapas e log em `private-diagnostics/qmp-candidate-artifacts/`,
com manifesto próprio. Não há pacote de instalação ou upload de release novo.

## O que ainda bloqueia o boot

Disponibilidade dos provedores QMP agora está demonstrada no artefato, mas
handshake/estado herdado Anorak não foram validados em hardware. Também faltam
captura antecipada de logs, posse da memória, CPUs, DMA/SMMU/dispositivos,
handoff compatível com CFI e revisão final dos bootargs. Nenhum resultado
autoriza salto, WARM, flash ou desativação de proteções.
