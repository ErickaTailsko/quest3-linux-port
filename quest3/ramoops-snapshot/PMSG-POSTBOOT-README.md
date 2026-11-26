# Paired PMSG post-reboot comparison

Use only after baseline_marker_verified=true for the padded marker test.
Do not run stage-pmsg-test.py again. Keep the existing test.json and before
capture unchanged. This package only adds a host comparator and its tests;
it does not modify the snapshot kernel module or write to the device.

One planned ordinary Android reboot is the next distinct test. Do not use
bootloader/recovery resets or cause a panic. Restore authorized ADB/root by
the existing Singularity workflow. Check su -c id returns uid=0. No extra
marker write is needed after the reboot. If the workflow changes kernel boot
identity multiple times, the comparator does not infer the number of resets.

Reload the existing q3_ramoops_snapshot module from /data/local/tmp. Collect
with the original collect-snapshot.py --out ~/quest3-pmsg-paired-test/after,
then unload the module. Preserve any error instead of forcing load/unload or
repeating the reboot. The output directory must be new.

Run:
python3 compare-pmsg-reboot.py --test ~/quest3-pmsg-paired-test --before ~/quest3-pmsg-paired-test/before --after ~/quest3-pmsg-paired-test/after --dtb ~/quest3-live-chunks.dtb

The comparator rechecks the real before snapshot rather than trusting the
baseline.json summary, requires a verified after snapshot/hash/size and a
changed kernel boot ID, derives PMSG layout from the supplied DTB, and checks
the token at its original byte offset with exactly one occurrence. A positive
marker_retention_confirmed confirms those raw bytes over the observed boot
change. It does not validate console recovery, late shutdown callback writes,
DMA preparation, CFI handoff, other reset modes or universal reliability.
Absent/shifted/duplicate bytes cannot identify the eraser. Kernel and reserved
memory layout must remain the same; the supplied DT is the baseline capture.

Send comparison.json, after/manifest.json and module unload status first.
Keep raw logs private. Do not publish diagnostic captures to the delivery host.

Host tests cover retained residual marker outside the new logical ring,
missing/overwritten/shifted/duplicate tokens, unchanged boot and corrupt hash.
To run tests locally with your captured DT:
python3 test-pmsg-compare.py --dtb ~/quest3-live-chunks.dtb
