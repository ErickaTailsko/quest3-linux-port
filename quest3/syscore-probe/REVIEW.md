# Syscore integration candidate

Verified source sequence: kernel_restart_prepare -> migrate_to_reboot_cpu ->
syscore_shutdown -> machine_restart -> optional EFI reset -> restart handlers.
register_syscore_ops/unregister_syscore_ops exported in stock Module.symvers.
Callbacks are void(void), a typed CFI-compatible interface.

syscore_shutdown (unlike syscore_suspend) does NOT itself disable IRQs;
it holds syscore_ops_lock and traverses registration list in reverse order.
The callback is consequently a plausible intermediate point, not yet proven
safe for multi-CPU shutdown. Current module is passive, default registration
OFF. observe=true changes only list registration; callback logs and returns.
Unregistration synchronizes via the same syscore mutex. No hardware test.

migrate_to_reboot_cpu increments hotplug disable count. A future owned restart
could balance its increment, remove secondaries and re-disable, but MUST
identify ownership and avoid balancing somebody else's transition. Other
hotplug disables may exist; the counter is private. Never force its value.
Holding syscore lock while CPU hotplug waits for callbacks/workers requires
a complete inversion review. Later-registered syscore callbacks execute first;
there is no priority field. No proof this observer runs before all shutdowns.

Additional decisive limitation: ARM SMMU driver .shutdown calls remove in the
public tree; device teardown and DMA context are already changed at syscore.
Successful hotplug while Android is running cannot establish hotplug safety
at this later point. Target must adopt the resulting firmware/SMMU state.

Next evidence would be a passive callback trace during an explicitly planned
normal reboot, with confirmed log retention/retrieval. Do not reboot just to
try this: ADB logging can disappear before callback and retention is unproven.
Compile/local lifecycle tests passed. No new device action currently required.
