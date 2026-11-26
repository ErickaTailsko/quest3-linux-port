# Passive Quest 3 handoff observer — compiled, NOT device-tested

This separate module does not modify quest_kexec. It observes three typed API
callbacks: blocking reboot notifier, syscore shutdown, atomic restart handler.
No reboot, CPU hotplug, SCM command, MMIO access or transition is issued.
By default observe=false and no callback is registered. observe=true would
register callbacks for a later reboot initiated elsewhere; do not deploy or
reboot for this until logs can be retrieved reliably after restart.

The restart callback always returns NOTIFY_DONE. Its INT_MAX priority does not
guarantee precedence over every installed callback (including earlier equal
priority callbacks). Some reset paths can skip these callbacks entirely.
CPU count, CPU ID, IRQ state and preemption depth are snapshots, not proof of
PSCI power-off or DMA quiescence. Logging can perturb timing. Host tests model
API registration and callback dispatch; they cannot validate hardware behavior.

The source kernel sequence is kernel_restart_prepare (notifier chain followed
by device_shutdown), migrate_to_reboot_cpu, syscore_shutdown, machine_restart.
On arm64 the restart-handler chain is after local_irq_disable and smp_send_stop.
Sleeping hotplug operations must not be placed in that final callback. At
syscore, device_shutdown has already run; arm_smmu_device_shutdown calls remove.
Successful CPU hotplug under normal Android runtime does not establish safety
in this later state. No CFI handoff backend is enabled by this observer.

Validation: build for stock 5.10.246-gd7102a837402; actual compilation uses CFI,
SCS and Full LTO; all imports are exported in stock Module.symvers; no restart,
CPU hotplug or private resolver import. test.py compiles the production source
against host stubs and checks disabled default, registration failures/unwind,
unrelated-event filtering, three returning callbacks, and unload cleanup.

To rebuild locally with the previously configured fish function:
    q3make -j4 M="$PWD" modules
To run host lifecycle tests:
    python3 test.py

No insmod, observe=true or reboot command is supplied for this delivery.
Pending: persistent/early capture, device shutdown and CPU ownership contract,
DMA/SMMU handling and a validated CFI-safe entry path. No production boot claim.
