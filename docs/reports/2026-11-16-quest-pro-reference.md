# Referência Quest Pro e revisão do alvo Quest 3

Fonte de apoio indicada pelo usuário: `/mnt/ssd/quest-kexec-main/`, em especial
`HOW_TO_PORT.md`. Revisão somente leitura desse diretório; nenhum script de
instalação, execução, reset ou leitura física do Pro foi executado no Quest 3.
Os resultados do Pro são declarações da referência, não testes reproduzidos aqui.

## Matriz de portabilidade

| Área | Referência Pro | Quest 3 / decisão |
|---|---|---|
| Primeiro alvo | BusyBox estático, sem discos, USB Ethernet | Mantido no Eris |
| Entrada Image | prepare.py exige offset `0x80000`, entrada `0x90080000` | Candidato tem offset zero, entrada `0x90000000`; não reutilizar prepare.py sem adaptação |
| Janela | `[0x90000000,0x93400000)` | Cabe nos dados capturados; posse contra alocação/DMA não demonstrada |
| Logger próprio | 64 KiB em `0x9ba80000` | Não transportar o endereço; está dentro de System RAM no iomem Quest 3, sem reserva correspondente identificada na revisão |
| Ramoops | read-log.sh também consulta pstore | Quest 3 tem reserva DT em `0xbfa00000`; snapshot já validado no mesmo boot |
| Símbolos privados | loader resolve kallsyms com kprobe | Eris mantém bloqueio CFI; endereço resolvido não valida tipo indireto |
| Retorno ARM64 | salva LR, mas não x18 no roundtrip observado | Preservar correção x18/LR do Eris; não regredir o frame |
| AOP/QMP | patch adiciona adoção `qkx_qmp_adopt=1`; guia manda não desconectar no Pro | Protocolos, driver e dependências precisam revisão específica; não passar parâmetro ao Quest 3 como solução pronta |
| GIC/SMMU | patches de estado SPI e tolerância a falha de bus voting | Não aplicar automaticamente; estabelecer contrato herdado e validar fontes do Quest 3 |
| Watchdog/reset | inclui MMIO fixo e reset WARM do kernel alvo | Sem equivalência demonstrada; não transportar endereços/rotas nem desabilitar proteções |
| USB e energia | patches de drivers e clocks Kona | USB2 DT Quest 3 revisado separadamente; nenhum patch Kona aplicado |

O logger Pro é inicializado no kernel ALVO, depois de `console_init`, e zera
sua própria área. Portanto, ele não resolve por si só a captura dos callbacks
finais do Android nem a disponibilidade de root antes dos consumidores. A
reserva precisa sobreviver também ao kernel anterior/firmware e ao retorno.

## Lacuna concreta do candidato atual

Na configuração publicada `quest3/ram-first-kernel/.config`:

- `CONFIG_MSM_QMP=m` e `CONFIG_QCOM_AOSS_QMP=m`.
- `CONFIG_MSM_CLK_AOP_QMP` não habilitado.
- GICv3, ARM SMMU, RPMh e pstore/ramoops estão embutidos.
- KEXEC nativo continua desabilitado; CFI continua habilitado.

O DT real contém `/soc/qcom,qmp-aop` e `/soc/qcom,qmp-tme`, compatíveis com
`qcom,qmp-mbox`. O System.map não contém símbolos `qkx_qmp_adopt` observados
no patch Pro. Isso não prova, isoladamente, que a adoção seja necessária no
Quest 3 ou que a configuração esteja errada. Mostra que não se pode presumir
que o mecanismo Pro exista no candidato ou que um provedor modular esteja
disponível no initramfs BusyBox mínimo. Revisar consumidores, ordem de probe,
dependências e protocolo antes de escolher módulos/built-ins ou portar patches.

Não foram alteradas configurações sem recompilar o Image correspondente.
Não há árvore completa de fontes/build do kernel nesta publicação.

## Procedimento offline executado com a captura atual

1. `prepare-dtb.py`: sete alterações USB permitidas; ambos os PHYs, demais
   propriedades e reservas preservados. Validação dtc independente não foi
   solicitada nesta nova geração.
2. `check-layout.py`: Image/initramfs/DT e iomem capturados no mesmo boot;
   criada cópia corrigindo apenas os dois endereços initrd de `/chosen`.

| Resultado | Valor |
|---|---|
| Entrada | `0x90000000` |
| Image size / fim | `0x2b20000` / `0x92b20000` |
| Initrd | `[0x93000000,0x9309145d)` |
| DTB | `[0x93200000,0x932aaa3c)` |
| DT USB2 SHA-256 | `21740f6d479b4fe921deae72cb39508afd7de861d448812e974152733b23e275` |
| DT com chosen corrigido SHA-256 | `147ae9900fe455734c7b9af1667ad14d397c3fce132cf16ce23bf5382db5ba98` |
| bootargs revisados / RAM reservada por esse teste | não / não |
| pronto para boot / boot testado | não / não |

Artefatos e JSON completos em `private-diagnostics/pmsg-same-boot-01/`.
Nenhum DT foi enviado ao aparelho ou aplicado ao vivo. Os bootargs herdados
ainda precisam de revisão antes de se considerar esse DT um payload diagnóstico.

## Identificação da cópia de apoio

Hashes SHA-256, sem atribuir um commit não verificado:

```text
02ab2b0cc2ae165a33d9411f8f487dfb5273cf50f5312d955331ab7a998a957b  HOW_TO_PORT.md
a49bc5cdf31a723dcc3b05c822905bf2d0440d934f04afdf7cc54038cc910afb  module/loader.c
12fff47223c8c8b3440849c2b212bd72b89f70127c63b4f8a8d7439fa825c3b7  module/transition.S
5c18d2918f46047b07d301693f01f94acbcb753f41deced3b3a8378d41cd5864  tools/prepare.py
563c77e1db773289f001bfcd73bba2cc7e6755b393617f8dbc4a5ee406d71878  tools/read-log.sh
```

## Próxima unidade de trabalho

Auditar AOP/QMP do candidato contra os consumidores do DT Quest 3 e o initramfs
mínimo; obter/revisar a árvore de kernel correspondente antes de alterar drivers
ou configuração. Em paralelo, manter pendente a captura inicial/externa: nenhum
resultado aqui autoriza `execute=1`, novo WARM, flash ou adoção de endereços Pro.
