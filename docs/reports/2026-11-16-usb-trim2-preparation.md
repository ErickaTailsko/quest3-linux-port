# USB trim2 — preparação e build iniciado

**Atualização de 2026-11-17:** Image concluiu e passou nas verificações;
image_size de 35,9375 MiB, ainda acima do trecho de 24 MiB observado.
[Resultado final](2026-11-17-usb-trim2-result.md). Estados pendentes abaixo são históricos.

Segundo perfil experimental, derivado do trim1 de 39,125 MiB. Configurado em
saída nova `.work/usb-trim2-config/`; compilação Image-only com dois jobs em
andamento. **Sem novo image_size medido ou teste no aparelho nesta etapa.**

## Escopo da redução

Removidos protocolos/recursos não usados pelo shell ECM IPv4 isolado: scheduler
de rede e classificadores, bridge, PPP/L2TP, CAN/802.15.4, vsock/vhost, interfaces
tun/veth/dummy/ifb, túneis e interfaces diagnósticas de sockets selecionadas.
XFRM de base, namespaces, UNIX sockets e PACKET não foram alvos dessa remoção.

Removidos filesystems de disco/rede não usados pelo `/init`: ext4, FAT/exFAT,
FUSE/overlay e outros roots já ausentes. Isso não significa ausência de todos
os drivers de disco: controladores de armazenamento e device-mapper foram
mantidos nesta fase. Proc/sysfs/devtmpfs/tmpfs/configfs e ptys continuam exigidos.

Áudio e seletores de DMA compartilhado permanecem como no trim1. Nenhum driver
novo foi ativado para mascarar dependência. Não é um kernel de uso geral,
Android, desktop ou rede roteada.

## Revisão e guardas

Diff incremental de 208 linhas revisado; inclui símbolos dependentes removidos,
não 208 recursos novos. Provedores explícitos de USB/QMP/RPMh/SMMU/shared DMA,
CFI/SCS/Full LTO/MODVERSIONS e as opções de hardening conferidas permaneceram.
SELinux/seccomp permanecem configurados; isso não valida política runtime.

Config SHA-256: `5bdae0670303ed5fa7dbe1bce6bf145279abba5c6fee0e1c63f3584cceb927c1`.
Release pretendido: `5.10.246-gd7102a837402-q3-usb-trim2`.

Arquivos públicos: trim2.fragment, trim2-preparation.json, trim2-config.diff em
`quest3/usb-trim/` e `quest3/configs/usb-trim2.config`. O helper de preparação
aceita `--profile usb-trim2`; baseline é a config trim1 publicada e ambos os
fragmentos são verificados, sem modificar as saídas anteriores.

## Reprodução

Após preparar as fontes/toolchain/pahole e patch host documentados, usar saída nova:

```sh
python3 tools/prepare-usb-trim.py --profile usb-trim2 --out .work/usb-trim2-new
Q3_OUT="$PWD/.work/usb-trim2-new" \
Q3_LOCALVERSION=-gd7102a837402-q3-usb-trim2 \
  tools/q3make -j2 HOSTCFLAGS=-DOPENSSL_NO_ENGINE Image
```

Só após retorno zero:

```sh
python3 tools/verify-qmp-candidate.py --out .work/usb-trim2-new \
  --profile usb-trim2 --image-only
```

O verificador passou a distinguir o release trim2 e recusar seus subsistemas
removidos se reaparecerem. Regressões continuam aprovadas: 32 testes host.
Resultado Image real permanece pendente; não se afirma redução suficiente,
reprodutibilidade binária, posse de RAM ou readiness para boot.

## Verificação adicional — 2026-11-17

Conferidos na configuração do build ativo INITRD/gzip, execução ELF e scripts,
TTY/ptys, UNIX/IPv4, filesystems em RAM e ECM. Os helpers de preparação e
verificação passaram a exigir esses requisitos, com regressões para recusar
ausência de BINFMT_SCRIPT ou RD_GZIP. Não houve alteração da configuração em
compilação. Os artefatos QMP e trim1 anteriores também passaram no verificador
ampliado. Suíte: 32 aprovações; build trim2 ainda sem resultado final nesta etapa.
