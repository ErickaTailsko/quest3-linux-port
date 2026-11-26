# Ordem de handoff — decisão técnica

Fonte disponível: kernel/kexec_core.c:kernel_kexec, caminho sem preserve_context:
1. kernel_restart_prepare(NULL) (notifiers, usermodehelpers, device_shutdown)
2. migrate_to_reboot_cpu
3. cpu_hotplug_enable
4. machine_shutdown -> smp_shutdown_nonboot_cpus
5. machine_kexec

Não executar shutdown de drivers com cpu_maps_update_begin mantido: callbacks
podem depender de hotplug, locks de dispositivos, workqueues e CPUs ativas.
A janela protegida de máscaras NÃO substitui essa sequência.

device_shutdown aguarda probe, bloqueia novos probes, suspende cpufreq,
percorre devices_kset em ordem reversa, retira entradas, mantém referências,
trava pai e filho, sincroniza runtime PM, invoca class shutdown_pre e bus
shutdown ou driver shutdown. Não é um percurso genérico bus_for_each_dev.
As entradas fundamentais não estão exportadas no Module.symvers stock.

GPU suspend, USB gadget disconnect, watchdog callbacks e CPU1 offline/online
não comprovam quiescência de todo DMA. DWC3 MSM e adreno têm remove no registro
de driver consultado; isso não é evidência de um shutdown global equivalente.
Continuam pendentes câmera, display, WLAN, DSP/remoteproc, armazenamento,
USB, SMMU e protocolos AOP/RPMh. Não desabilitar SMMU genericamente.

Decisão: NÃO integrar salto ao protótipo multi-CPU nem liberar execute.
Um inventário de drivers é diagnóstico, não uma prova de parada do hardware.
É preciso estabelecer um mecanismo de shutdown do kernel stock compatível
com CFI e sua semântica, ou outra entrada validada. Kernel de destino com
novos exports não resolve o kernel stock atualmente em execução.
A restrição não demonstra impossibilidade do porte, mas impede prometer
boot funcional com as correções e APIs verificadas até aqui.
