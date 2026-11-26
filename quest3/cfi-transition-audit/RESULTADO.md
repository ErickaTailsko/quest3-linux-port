# Transição CFI — auditoria do kernel disponível

O preflight no aparelho passou; isso não valida qkx_execute.
O loader possui 18 nomes privados resolvidos por lookup; comparar result.json
com Module.symvers. Não foi removido o bloqueio CONFIG_CFI_CLANG.

remove_cpu/add_cpu são exportadas, mas envolvem lock_device_hotplug e
 device_offline/online; não são substituições textuais de cpu_down/cpu_up.
stop_machine mantém CPUs executando código do kernel antigo; não permite
sobrescrever livremente memória usada por esses CPUs.
kernel_restart é exportada, porém executa syscore_shutdown e machine_restart,
que chama smp_send_stop antes dos restart handlers. Não equivale ao caminho
machine_shutdown/smp_shutdown_nonboot_cpus usado por kexec ARM64.
register_restart_handler permite callback tipado sob CFI, mas não resolve
por si só CPU hotplug, DMA, GIC/SMMU, firmware e contrato de entrada.
freeze_processes/thaw_processes/device_shutdown não estão exportadas.

Conclusão: não foi demonstrada uma sequência de handoff completa usando
somente as APIs exportadas do kernel stock fornecido. Isso não prova que
um porte seja impossível; exige nova implementação arquitetural e validação.
Não usar __nocfi, endereços de kprobe como função ou alterações de flags como
se fossem uma solução que preserva CFI. Exportar funções no kernel de destino
não modifica o kernel stock atualmente executando no aparelho.

Próxima implementação possível: backend novo com APIs exportadas, contrato
explícito de CPU hotplug e quiescência, seguido de ensaios reversíveis separados.
Somente depois integrar shutdown e trampoline. O caminho atual permanece
-EOPNOTSUPP. Nenhum reboot, escrita de firmware ou teste de CPU foi executado.
