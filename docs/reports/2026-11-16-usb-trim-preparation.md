# Redução USB do alvo — preparação do primeiro perfil

**Atualização final:** build concluído e artefatos verificados. Image_size caiu
para 39,125 MiB, ainda acima de 24 MiB; veja o
[resultado](2026-11-16-usb-trim-result.md). Os estados pendentes abaixo são históricos.

## Medição inicial

O vmlinux QMP completo foi medido com llvm-size:

| Classe de seção | Bytes |
|---|---:|
| text/readonly segundo llvm-size | 30.549.048 |
| data | 12.874.966 |
| bss | 1.597.464 |

Esses valores não substituem image_size=45.219.840 bytes do Image. Também não
se deve somar tamanhos de todos os símbolos como se fossem disjuntos: há aliases
e entradas CFI. A listagem completa de símbolos foi preservada privadamente.
CFI não foi selecionado para remoção para reduzir tamanho.

## Iterações de configuração e recusas

1. Redução inicial recusada: MEDIA_SUPPORT voltou por seletores GKI.
2. Revisada a cadeia GKI; HID voltou por USB_HID e também foi tratado no plano.
3. Draft sem áudio fazia DMA_VIRTUAL_CHANNELS cair de built-in para módulo;
   a revisão detectou isso. Tentar atribuir y diretamente ao símbolo escondido
   não bastou, e essa preparação foi recusada.
4. Perfil final desta etapa mantém áudio e seus seletores. Nenhum controlador
   DMA novo foi habilitado para mascarar a dependência.

Diretórios intermediários foram preservados em .work. Configuração final em
`.work/usb-trim1-final-config/`, sem substituir os candidatos anteriores.

## Estado aprovado para compilação

`tools/prepare-usb-trim.py` gerou a config separada, mantendo os provedores
USB/QMP/RPMh/SMMU explícitos, shared DMA e os requisitos CFI/SCS/LTO/MODVERSIONS.
SELinux, seccomp e opções de hardening selecionadas foram comparadas à baseline.
Foram removidos stacks de media/display, HID, wireless/Bluetooth, netfilter,
IPv6 e USB storage. A rede alvo permanece IPv4 ECM em link direto isolado,
sem firewall netfilter, Wi-Fi ou intenção de uso como sistema geral.

O diff de 786 linhas inclui símbolos que desapareceram por dependências e
opções já n, não significa 786 novos subsistemas removidos. Os provedores
explicitamente exigidos passaram nas verificações; hardware não foi validado.

Config SHA-256: `8cf9e3a6ebf7e7136ee706240168efc435254e1d148a3fb1a86e42abaf8dc29c`.
Versão local: `-gd7102a837402-q3-usb-trim1`.

## Reprodução da preparação

Uma segunda preparação independente em `.work/usb-trim1-repro-check/` produziu
config, diff e JSON idênticos byte a byte. Uma nova chamada para a mesma saída
foi recusada, preservando o hash da configuração. Registro público em
`quest3/usb-trim/trim1-repro-check.json`. Isso não é teste de reprodutibilidade
do binário kernel, que ainda não foi concluído nesta atualização.

## Build iniciado, resultado ainda pendente

Compilação de Image, dois jobs, toolchain/pahole fixados e correção OpenSSL host
documentada. Não se pediu o conjunto completo de módulos, pois o CPIO mínimo
não os inclui. Log: `.work/usb-trim1-final-config/build-image.log`.

Ainda não foi medido o novo image_size nem demonstrado que caiba em 24 MiB.
Não há nova base de RAM, aquisição, DT ou teste no Quest. Mesmo uma redução
suficiente não resolve posse de páginas, DMA, logging inicial ou handoff CFI.

Verificador recebeu perfil explícito usb-trim1 e modo image-only, com testes
para release separado, exclusão de DRM e tabela vmlinux.symvers. Suíte host
permanece com **32 aprovações**. O build final deve ser verificado separadamente.
