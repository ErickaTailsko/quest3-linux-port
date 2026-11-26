# Quest 3 reversible WARM policy guard — no reboot request

First device step: verify COLD -> WARM -> COLD without reboot. Do not combine
this cycle with adb reboot. The controller unloads the guard before returning.
This is a real temporary reset-policy change, not a firmware reset experiment.
While armed, an independently initiated reboot/panic fallback can consume the
WARM policy. Physical forced-power recovery remains relevant to any later firmware reset
test. Root-on-boot is independent of alternative kernel startup.

The module imports exported reboot_mode and panic_reboot_mode. Default arm=0
reads state only. arm=1 atomically changes only REBOOT_COLD to REBOOT_WARM,
rejecting other current values. Unload restores the saved mode only if the
value still equals WARM. It does not force another actor's different value.
Identical-value ABA from an external WARM writer cannot be detected; this is
not global ownership or synchronization against other reset controllers.
Do not run parallel module/reset-policy controllers during this check.
No fallible setup follows a successful policy mutation. panic_reboot_mode is
read, never modified; UNDEFINED can inherit WARM while the guard is armed.
The module calls no reboot, firmware, CPU hotplug or private-symbol interface.

check-guard-cycle.py reserves a new local report, requires authorized root and
sys.boot_completed=1, checks remote module hashes and pre-existing modules,
reads original mode with the previously tested q3_reset_mode_info module,
checks default guard inspection, arms and checks mode=1/ownership=1, unloads,
and reads the restored mode independently. Cleanup is attempted in finally,
including when insertion succeeded but its reply was lost. An ADB loss or
failed unload can leave the policy armed; the report will remain incomplete.
No script can guarantee cleanup while the device is unreachable. Reconnect
and unload q3_warm_reset_guard before initiating any reboot in that case.
Pre-existing modules are refused instead of deliberately taken over.

The existing /data/local/tmp/q3_reset_mode_info.ko must remain available and
match the already tested SHA256 f155e03cce28479b3eb38546d2b1f9d3c73c16a80e15e1833b79ea3f230f39f3.
The new uploader installs only the guard temporary file, using the previously
verified idempotent block transfer, and does not load modules or request reset.

Commands from this directory after SHA256SUMS verification (fish):
    python3 push-warm-guard.py
    and python3 check-guard-cycle.py --out ~/quest3-warm-guard-cycle.json

Expected passed checkpoints: before0, inspection0, armed1, after-unload0.
Send quest3-warm-guard-cycle.json. Do not write another PMSG marker or reboot
for this step. The original COLD retention failure and captures remain intact.

## Source review
kernel/reboot.c exports reboot_mode, passes it to the atomic restart chain.
drivers/firmware/qcom_scm.c qcom_scm_do_restart (priority130) invokes its OEM
power reset only for REBOOT_WARM. drivers/firmware/psci/psci.c (priority129)
selects SYSTEM_RESET2 for WARM/SOFT only if its support flag was discovered,
otherwise SYSTEM_RESET. These are source paths, not proof of the live last
handler, firmware success, DRAM retention, or safety of a new reset mode.
The legacy msm-poweroff force_warm_reboot private variable is not used.

## Validation
Stock kernel ABI 5.10.246-gd7102a837402; CFI, SCS and Full LTO; all imports
exported; linked atomic instruction present; no reset/notifier/firmware import.
Production C ownership helper tests cover acquisition, duplicate ownership,
rollback and a foreign value. Actual controller tests inject hash/boot gates,
pre-existing module, lost arm reply, read failure, unload failure and foreign
policy. Host tests do not exercise actual firmware or prove device cleanup.
This guard and its cycle have not yet been tested on the Quest.

Rebuild: q3make -j4 M="$PWD" modules
Host tests: python3 test-state.py; python3 test-cycle.py
A subsequent firmware reset and a new paired-retention test remain separate.
