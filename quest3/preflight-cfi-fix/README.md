# Preflight independente compatível com CFI

Compilado para 5.10.246-gd7102a837402. Mantém Full LTO, CFI e Shadow Call Stack, além das correções anteriores.

No aparelho, com privilégios de root e o módulo anterior descarregado, a opção nova é:

```sh
insmod quest_kexec.ko preflight_only=1
```

execute fica em 0. Ao terminar a consulta de logs, o módulo pode ser descarregado com `rmmod quest_kexec`. Nenhum desses comandos foi executado no headset nesta sessão.

O preflight confere a placa qcom,anorak, prontidão do driver SCM, vínculo DWC3/gadget/pullup e driver Gunyah watchdog ativo com tarefa/callbacks válidos. Obtém e libera referências e locks; não chama disconnect/connect, callbacks do watchdog, timers, comandos SCM, freezer, nem prepara imagens/memória de staging. Não precisa dos arquivos Image/initrd/DTB de destino. O DT e os drivers examinados pertencem ao kernel em execução.

Todas as combinações com execute, testes, controles SCM, flags de watchdog, QMP/RPMh/syncboss ou phase_delay_ms são recusadas com -EINVAL antes do acesso aos dispositivos. Em particular, a combinação antiga `execute=1 preflight_only=1` agora é inválida. Parâmetros de caminho das imagens não são utilizados por este modo.

Sucesso confirma apenas os vínculos e operações presentes, sem garantir que firmware/USB/watchdog responderão corretamente quando acionados. Ausência de dispositivo/driver gera erro; watchdog inativo é recusado. Execução kexec, ensaios preflight 2/3, testes de CPU, warm reset e usb_log continuam bloqueados sob CFI. O mapa das 25 dependências restantes do resolvedor está em remaining-private-symbols.md; 5 constam como exportadas, mas o código legado ainda as chama pelo resolvedor e continua bloqueado.

Validação: compilação sem erros/avisos novos; CRC/BTF/configuração/CFI/SCS aprovados. Testes host do código de produção confirmam sucesso/falha do preflight sem callbacks de hardware e rejeição de 15 modos combinados antes de consultar a placa. Testes de regressão USB/watchdog/SCM passaram. Não houve teste de concorrência real, carga do módulo ou salto no aparelho.

O patch incremental aplica sobre o pacote USB/watchdog anterior e passou por git apply --check. A pasta module contém os fontes completos e os módulos. Os scripts de auditoria pressupõem o workspace /workspace/quest3-build com kernel, toolchain e entradas originais; esses componentes não estão neste pacote.
