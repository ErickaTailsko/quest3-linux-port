# Referências privadas restantes

O loader ainda contém 18 referências a símbolos não exportados nesta compilação, incluindo o código QMP desativado. Os modos que precisam do resolvedor permanecem bloqueados sob CFI.

As cinco chamadas exportadas já foram migradas para APIs diretas. As duas chamadas Adreno foram migradas para dev_pm_ops do driver kgsl-3d, sem nomes privados nem casts.

| Símbolo | Exportado |
|---|---|
| `__boot_cpu_mode` | Não |
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

O preflight independente não usa o resolvedor e não executa callbacks PM. As dependências centrais de freezer/desligamento/CPUs exigem uma API alternativa validada ou integração ao kernel de destino; retirar CFI não resolve a compatibilidade.
