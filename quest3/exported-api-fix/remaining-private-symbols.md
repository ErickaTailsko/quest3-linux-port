# Dependências restantes do resolvedor privado

As cinco dependências exportadas foram convertidas para chamadas diretas com os cabeçalhos oficiais. Permanecem 20 símbolos não exportados nesta compilação, incluindo funções e dados. Todos os modos que dependem do resolvedor continuam bloqueados sob CFI.

| Símbolo | Exportado |
|---|---|
| `__boot_cpu_mode` | Não |
| `adreno_pm_resume` | Não |
| `adreno_pm_suspend` | Não |
| `cpu_down` | Não |
| `cpu_up` | Não |
| `cpus_are_stuck_in_kernel` | Não |
| `enable_nonboot_cpus` | Não |
| `events_check_enabled` | Não |
| `force_warm_reboot` | Não |
| `freeze_processes` | Não |
| `freeze_secondary_cpus` | Não |
| `kernel_restart_prepare` | Não |
| `kexec_in_progress` | Não |
| `machine_restart` | Não |
| `machine_shutdown` | Não |
| `migrate_to_reboot_cpu` | Não |
| `pm_abort_suspend` | Não |
| `qmp_shutdown` | Não |
| `send_irq` | Não |
| `thaw_processes` | Não |

O preflight independente não usa o resolvedor. A ausência de exportação exige uma API alternativa validada ou uma mudança no kernel de destino; remover CFI ou usar endereços obtidos via kprobe não resolve essa compatibilidade.
