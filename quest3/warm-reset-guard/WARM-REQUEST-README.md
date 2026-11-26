# One-shot guarded WARM request controller

The reversible COLD/WARM/COLD cycle has been observed on the device. Firmware
WARM reset and retention remain untested. This package adds only a host script
and tests; no kernel binary is changed. The existing 1b1e60... guard is used.

First create a NEW marker test directory and before capture with the existing
stage-pmsg-test.py, collect-snapshot.py and check-pmsg-baseline.py tools.
Do not reuse the failed COLD test marker. The baseline must be valid and its
boot ID must still match the currently running kernel. Preserve the old test.
The existing root-on-boot workflow is independent of alternative kernel boot.

Default invocation only reads preflight state; it does not load a module,
alter policy or reboot:
python3 request-warm-reboot.py --test ~/quest3-pmsg-warm-test --dtb ~/quest3-live-chunks.dtb

The explicit --reboot-now option is the commit action. It is intended only for
a separately planned first firmware reset test after the new baseline passes.
It verifies root/Android boot complete, the before snapshot's hash and unique
marker, current boot identity, previous reversible cycle report, guard absence
and exact remote module SHA. It reserves warm-request.json with exclusive
creation, inserts the guard with arm=1 and confirms live mode1/ownership1.
It fsyncs provenance BEFORE requesting one ordinary adb reboot without a target
name. No private call, bootloader mode or direct firmware command is used.
The exported mode policy selects the kernel's SCM/PSCI route.

Before commit, errors attempt to unload the newly inserted guard. A missing
ADB response can prevent cleanup; reconnect and inspect/unload before any
reset. After commit starts, NO automatic mode reversal or retry is done:
device_shutdown can already be running, and a failed/lost ADB reply does not
prove cancellation. A second invocation for the same test is refused. If the
request is uncertain, inspect device/boot identity and preserve the report;
do not send another reboot just to discover what happened. Physical forced
power recovery, if used, makes the requested firmware path unproven.

When the device is reachable again, restore root as usual, load only the RO
snapshot module, collect NEW_DIRECTORY/after and unload that reader. Use the
existing compare-pmsg-reboot.py with the same new test directory. Do not write
the marker again after reboot. Keep warm-request.json with the comparison.
The policy guard disappears on a kernel reset; it has no persistent boot hook.
A successful ADB acknowledgement or mode1 before request does not prove which
firmware handler completed reset. Raw marker retention, late callback logging,
CFI handoff and universal reset reliability are separate conclusions.

Local model tests run the production controller against simulated ADB: default
read-only preflight, stale boot/hash/pre-existing guard rejection, one request,
commit provenance, no automatic unload after commit, precommit rollback,
uncertain replies and duplicate commit refusal. Real uploaded baseline data
was also checked end-to-end through the production decoder/import chain with
simulated ADB preflight only. No actual WARM reset has yet been issued.

Send warm-request.json, comparison.json and after/manifest.json after a test.
Raw snapshots remain private. Do not publish them to the delivery host.
