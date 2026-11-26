# DT diagnóstico do candidato QMP

**Preparação offline concluída; nenhum arquivo aplicado ao aparelho.**

O helper `quest3/layout-review/prepare-bootargs.py` agora recebe caminhos
explícitos `--input`/`--out`, exige Quest 3 Eureka/Anorak e saída nova, e verifica
que apenas `/chosen/bootargs` foi alterado. Não depende mais de caminhos fixos
no diretório home. Entradas com aspas, escapes ou NUL embutido são recusadas
em vez de tentar reinterpretar argumentos ambíguos.

## Política revisada

- Remove `root`, `rootfstype`, `rootflags`, `rootdelay`, `rootwait`, `init`,
  flags ro/rw e bootconfig da linha de comando herdada.
- Retira console=none, configuração específica de display e parâmetros dload
  selecionados pelo helper histórico.
- Define uma única ocorrência de `rdinit=/init`, `loglevel=7`, `log_buf_len=1M`,
  `panic=0` e `pstore.compress=none`.
- Preserva os demais parâmetros da captura: isso não é uma revisão completa
  das opções de plataforma, energia, mitigação ou firmware.

O kernel candidato possui CONFIG_CMDLINE vazio; CONFIG_BOOT_CONFIG está
habilitado, mas o initramfs mínimo verificado não inclui bootconfig adicional.
`panic=0` não desabilita watchdogs ou garante ausência de resets por firmware.
`loglevel=7` permite mensagens informativas no console normal, não garante
retenção, saída externa ou persistência depois de reset.

## Artefatos e checagens

DT de origem: cópia USB2 com initrd corrigido da captura atual.
Resultado local: `private-diagnostics/qmp-audit/candidate-diagnostic.dtb`.

SHA-256: `212b80a051570874811ef504dcf4356cfd4226a262851dd84ed0c70089be8a09`.

Layout rechecado com o novo Image QMP e CPIO USB2:

- entrada `0x90000000`, fim Image `0x92b20000`;
- initrd `[0x93000000,0x9309145d)`;
- DT `[0x93200000,0x932aa998)`;
- chosen initrd confere e não houve sobreposição detectada nas reservas
  DT/iomem capturadas. Isso não reserva a RAM contra alocação ou DMA.

Metadados de layout publicados em
`quest3/qmp-audit/candidate-diagnostic-layout.json`. O campo
`bootargs_reviewed=false` desse verificador foi preservado: ele não analisa
política de argumentos. A revisão limitada RAM-first está descrita aqui;
não deve ser confundida com validação de todas as opções herdadas.

## Testes

`quest3/layout-review/test-bootargs.py` cobre remoção de raiz em disco,
normalização de argumentos duplicados, compatibilidade da placa, rejeição de
entradas ambíguas, mudança de propriedade única, idempotência e sobrescrita
recusada. Integrado à suíte: **26 aprovações, zero falhas/ignorados**.

## Próxima etapa

Revisar o backend de handoff CFI e o contrato de memória/CPUs/dispositivos,
mantendo a captura antecipada como bloqueio de ensaios irreversíveis. Esse DT
não deve ser aplicado ao Android ao vivo e não libera execute=1 ou reset.
