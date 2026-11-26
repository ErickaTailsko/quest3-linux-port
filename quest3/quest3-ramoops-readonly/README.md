# Quest 3 ramoops read-only forensic snapshot

This delivery does NOT establish reliable log retention. It creates a new
read-only diagnostic to look for older marker bytes even after record headers
were reset or files unlinked. No reboot is needed for this initial collection.

## Kernel module
q3_ramoops_snapshot is separate from quest_kexec. It requires Anorak/Eureka,
a ramoops node directly under /reserved-memory, a single 64-bit address/size
reg entry, mem-type=0, at most 1MiB, page-aligned bounds, and an active ramoops
driver bound to that DT node. It refuses mixed valid/invalid PFNs and refuses
non-PageReserved normal RAM. It has no arbitrary-address module parameter.
Mapping cache attributes follow stock ram_core.c. No private driver layout,
kprobe, SCM command, CPU hotplug, reboot callback or write to the mapped
reservation is used. It copies data once, unmaps, and exports the immutable
copy at /sys/kernel/q3_ramoops_snapshot/data, root-readable mode 0400.
Concurrent console/pmsg writers can affect the original copy: this is not an
atomic live snapshot. The module's final printk occurs after the copy.

## Local steps (fish; no reboot)
Verify SHA256SUMS first. Existing ADB root must work. Do not disable guards if
loading refuses the current layout. If the module is already loaded, stop
and inspect it instead of assuming it belongs to this collection.

    modinfo -F vermagic q3_ramoops_snapshot.ko
    adb push q3_ramoops_snapshot.ko /data/local/tmp/q3_ramoops_snapshot.ko
    and adb shell "su -c 'insmod /data/local/tmp/q3_ramoops_snapshot.ko'"

After successful insertion:

    python3 collect-snapshot.py --out ~/quest3-ramoops-readonly
    set -l collected $status
    adb shell "su -c 'rmmod q3_ramoops_snapshot'"
    if test $collected -eq 0
        python3 analyze-snapshot.py --snapshot ~/quest3-ramoops-readonly/ramoops.bin --dtb ~/quest3-live-chunks.dtb > ~/quest3-ramoops-readonly/analysis.json
    end

collect-snapshot.py only reads an already-loaded module, verifies root, boot
identity, byte count and remote/local SHA256, and retries small transfers.
4KiB dd reads handle sysfs short reads. No local output directory is overwritten.
Collection failure leaves manifest.json incomplete and no verified ramoops.bin.
The collector itself does not install, unload, reset, change properties or
write on the device. The ADB push above writes only a temporary module file.
If ADB disconnects before cleanup, unload the module when ADB returns.

Send analysis.json and manifest.json first. The raw snapshot can contain
private device logs: keep it local and do not publish it to the delivery host.

## Interpretation
analyze-snapshot.py calculates the exact zone layout from the supplied DTB,
requires matching size and the reviewed non-ECC/non-per-CPU format, and searches
both logical rings and residual data. It knows the old console/PMSG markers and
the observer prefix. Neither a positive residual hit nor an empty result proves
retention across a particular reboot without paired boot provenance. Absence
cannot distinguish overwriting, erasure or firmware reset. Original kernel
5.10.246 signatures are assumed. No ftrace region is treated as free memory.
No writer or alternate persistent logger is included.

## Validation scope
Stock ABI 5.10.246-gd7102a837402; CFI, SCS, Full LTO; all imports exported.
Host tests compile production copy/read bodies, exercise normal reserved pages,
non-PFN mappings, mixed/unreserved PFN refusal, mapping/allocation failures,
read boundaries and unchanged source bytes. Tool tests cover residual vs logical
markers, ring wrap, malformed headers, truncated snapshots, ADB retry, root,
checksums, boot changes and output overwrite. Hardware has NOT been tested.

Rebuild with the existing toolchain wrapper:
    q3make -j4 M="$PWD" modules
Host tests:
    python3 test-copy.py
    python3 test-tools.py --dtb ~/quest3-live-chunks.dtb
