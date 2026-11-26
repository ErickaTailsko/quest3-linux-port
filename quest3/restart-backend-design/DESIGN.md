# Backend via kernel_restart: design, NOT implemented kernel handoff

Actual device observation: EFI_BOOT=0, EFI_RUNTIME_SERVICES=0,
RESET_SYSTEM_SUPPORTED=0. Other gates remain unproven.

Critical distinction: kernel_restart_prepare ignores the return value of the
blocking reboot notifier chain. NOTIFY_BAD/STOP cannot cancel kernel_restart.
Therefore all fallible prerequisites must be resolved BEFORE kernel_restart;
a notifier is not a safe validation/rollback hook. It runs before device
shutdown and is not a post-DMA-quiescence notification.

Final restart handler is atomic, after local IRQ disable and smp_send_stop.
It cannot remove_cpu/add_cpu, sleep, allocate with GFP_KERNEL, freeze users,
wait for workers, perform fallible preparation or assume normal driver APIs.
SCM restart priority 130 and PSCI priority 129 in the public source. A priority
above those is not proof of precedence over all live handlers. Source may
not match every private module; do not claim a complete live inventory.

Phases:
1. PREPARE: stage/verify/reserve payload+log, module lifetime and exact request
   ownership; reversible checks only. No reboot handler armed for general reboots.
2. READY: need proven CPU protocol, DMA/device shutdown contract, callback
   order and atomic trampoline, plus current EFI facts.
3. COMMIT: kernel_restart; no return-to-Android rollback promise after this.
4. FINAL: accept only matching armed request; recheck entry invariants without
   sleeping. No allocations, hotplug, locks requiring sleep or driver operations.
5. ENTRY: nonreturning trampoline if all proven; otherwise continue the existing
   reset chain (NOTIFY_DONE), not NOTIFY_STOP which may leave the machine halted.
   Existing reset chain is only a fallback candidate, not proven recovery.

Unresolved: early CPU offlining before device_shutdown differs from native
kexec order; late CPU offlining from an atomic callback is invalid. A validated
intermediate mechanism is required. This design does NOT bypass that obstacle.

phase_model.py tests decisions only; no hardware semantics, DMA or CFI validated
by the model. No reboot/notifier registration or device mutation performed.
