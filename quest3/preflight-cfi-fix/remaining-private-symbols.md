# Dependências restantes do resolvedor privado

Obtido do loader.c e Module.symvers da compilação atual. Exportação permite estudar uma chamada direta com protótipo correto; não valida a operação nem libera o caminho de execução.

| Símbolo | Exportado nesta compilação | Provedor |
|---|---|---|
| `__boot_cpu_mode` | Não | — |
| `adreno_pm_resume` | Não | — |
| `adreno_pm_suspend` | Não | — |
| `cpu_down` | Não | — |
| `cpu_hotplug_enable` | Sim | vmlinux |
| `cpu_up` | Não | — |
| `cpus_are_stuck_in_kernel` | Não | — |
| `enable_nonboot_cpus` | Não | — |
| `events_check_enabled` | Não | — |
| `force_warm_reboot` | Não | — |
| `freeze_processes` | Não | — |
| `freeze_secondary_cpus` | Não | — |
| `kernel_restart_prepare` | Não | — |
| `kexec_in_progress` | Não | — |
| `lock_system_sleep` | Sim | vmlinux |
| `machine_restart` | Não | — |
| `machine_shutdown` | Não | — |
| `migrate_to_reboot_cpu` | Não | — |
| `pm_abort_suspend` | Não | — |
| `qmp_shutdown` | Não | — |
| `rpmh_write_sleep_and_wake` | Sim | drivers/soc/qcom/qcom_rpmh |
| `send_irq` | Não | — |
| `set_cpus_allowed_ptr` | Sim | vmlinux |
| `thaw_processes` | Não | — |
| `unlock_system_sleep` | Sim | vmlinux |

O preflight_only=1 independente não usa este resolvedor. Execução, ensaios 2/3, testes de CPU e warm reset continuam bloqueados sob CFI.
