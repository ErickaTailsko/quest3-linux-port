# Linha do tempo reproduzível — 2026-11-16

Foi adicionada a ferramenta offline `tools/analyze-startup-timeline.py`, sem
ADB, escrita no aparelho ou execução de comandos remotos. Ela cruza um dmesg,
eventos logcat em formato monotônico e um registro procfs do processo Magisk.

## Resultado nas evidências preservadas

| Evidência | Tempo desde o início do kernel |
|---|---|
| Primeira tela nos eventos preservados | 15,130 s |
| Início do processo Magisk observado | 69,490 s |
| Segunda tela nos eventos preservados | 80,365 s |
| Primeiro timestamp no dmesg preservado | 80,386282 s |
| Início observado do panicreporter | 80,461494 s |
| Saída observada do panicreporter | 80,575310 s |

O trecho dmesg começa tarde demais para excluir um consumidor anterior ao
Magisk. Além disso, início de processo não prova que `su` ou um hook já estavam
operacionais naquele instante. Eventos repetidos do framework não provam
resets do kernel. **A captura anterior a todos os consumidores segue pendente.**

## Reprodução local

As entradas abaixo são privadas e estão ignoradas pelo Git; o resultado não
é necessário para executar os testes sintéticos públicos.

```sh
python3 tools/analyze-startup-timeline.py \
  --kernel-log private-diagnostics/2026-11-16/eris-quest3-live-20261116-02/kernel-log.txt \
  --events-log private-diagnostics/2026-11-16/eris-root-startup-01/boot-event-times.txt \
  --magisk-stat private-diagnostics/2026-11-16/eris-root-startup-01/process-start-times.txt \
  --clock-ticks 100
```

`CLK_TCK=100` foi medido no aparelho; não se usa o valor do host. A primeira
linha de `--magisk-stat` deve ser o registro `/proc/PID/stat` de `magiskd`.
As entradas precisam corresponder à mesma sessão/boot e à mesma base de tempo;
a ferramenta não autentica essa procedência nem identifica processos históricos
ausentes. O JSON da sessão foi salvo em `private-diagnostics/startup-timeline.json`.

## Testes e continuidade

`tools/test-startup-timeline.py` cobre conversão de ticks, cores ANSI, múltiplos
eventos do framework, consumidor anterior ao Magisk, logs ausentes e metadados
inválidos. Está integrado à suíte host: **24 aprovações, zero falhas/ignorados**.

Próxima evidência necessária: disponibilidade real do mecanismo de captura
antes da primeira execução de consumidores, com cobertura inicial verificável,
ou transporte independente validado. Não instalar hook nem solicitar reset
apenas por existir uma janela antes da última execução observada.
