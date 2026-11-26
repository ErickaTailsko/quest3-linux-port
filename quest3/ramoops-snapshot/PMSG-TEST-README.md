# Padded PMSG baseline preparation

This is a new test using the existing /dev/pmsg0 userspace interface plus the
read-only raw capture already tested on the Quest. It is not a new persistent
kernel logger. It does not enable the handoff observer or any reboot/jump.

stage-pmsg-test.py --out NEW_DIRECTORY writes 65536 zero bytes and a unique
49-character marker plus newline through /dev/pmsg0. This consumes about64KiB
of diagnostic ring history. Preserve the original raw capture before this test.
The module/kernel/partitions are not changed by this script. A uniquely named
/data/local/tmp payload file is transferred in idempotent blocks, checked by
SHA256, used once, then removed. The PMSG write is attempted exactly once even
if the ADB response is lost. test.json records the result; never repeat a write
just because its response failed. The output directory cannot be overwritten.

After stage, reload the existing q3_ramoops_snapshot module and use the existing
collect-snapshot.py --out NEW_DIRECTORY/before, then unload the module. Both
module and collector are already in the original quest3-ramoops-readonly package.
check-pmsg-baseline.py --test NEW_DIRECTORY --capture NEW_DIRECTORY/before
--dtb ~/quest3-live-chunks.dtb validates the capture hash and same boot, derives
the region from DT, verifies the marker in the logical ring and raw bytes,
requires a single occurrence in the upper half with an end margin, and reports
baseline_marker_verified. A positive result confirms only the baseline.
Retention remains false until a separate post-reboot capture locates the same
token with changed boot identity. No reboot command is provided in this stage.
The local ADB files/module remain available after unloading for later reads.

If any step fails, preserve test.json and capture manifest; do not repeat the
marker write or run an unverified reset. Existing files are never overwritten.
A negative baseline means do not use it for a retention test. Multiple ADB
devices must not be attached simultaneously (standard adb selection is used).

Host tests exercise the actual scripts with a simulated device: padded payload,
SHA256 gate, exactly one marker write even when reply times out, cleanup,
verified upper-half position, matching boot identity and capture integrity.
No hardware marker write has yet been performed with this new test.
