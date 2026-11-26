# Normal reboot retention test: inconclusive / marker not recovered
Before boot_id: 1ab24359-9e90-48c0-9195-a541bdda62ae
After boot_id: 9653d9d1-799b-48dd-bd0c-de3c20a7309a
Marker Q3_PSTORE_TEST_KGLaZm_01 observed in live dmesg before reboot.
After archive contains valid pstore.tar with only directory '.', no records.
Marker absent from captured current dmesg. No pstore/ramoops initialization
messages in captured current dmesg window. Cannot distinguish RAM lost/reset,
record overwritten, backend issue or userspace archive/removal from this data.
Do not mark retained logging validated or proceed with syscore reboot probe.
Next read-only check: Android DropBox SYSTEM_LAST_KMSG and boot logcat for
pstore/BootReceiver processing; no further reboot until collected.

## Additional device evidence
ro.boot.bootreason and sys.boot.reason both reboot,shell (does not establish
warm vs cold hardware reset or DRAM retention).
/system_ext/etc/init/ovr_crashreporter.rc explicitly comments:
"allow panicreporter to clean up pstore after collecting the report",
then chmod 0750 /sys/fs/pstore. This identifies a potential consumer/remover;
it does NOT prove a record existed, was archived or deleted in this boot.
Android DropBox has no SYSTEM_LAST_KMSG entry. Need exact crashreporter service
configuration and focused logs to locate its output before another reboot.

## Crashreporter init confirmed
panicreporter is oneshot /system_ext/bin/ovr_crashreporter64 -k, user system,
groups system log; started at sys.boot_completed=1. Same property starts
crashreporterd (-c). post-fs-data creates /data/misc/crashes and minidumps
and permits pstore cleanup. Actual output path for -k not established by rc.
Full supplied logcat window contains no panicreporter/pstore processing event;
QC2CompStore matches were unrelated. Cannot infer the collector ran or erased
records from this log window. Next inspect output filenames and path strings
in the executable read-only, without invoking -k or changing services.

## libovr_crashreporter strings
Symbols include KernelCrash::CollectFromPstore, collectFromPstoreImpl,
purgePstoreDirectory, for_each_ramoops, hasKernelPanicImpl and
 dmesgHasPanicPhrase. Messages explicitly mention dropping non-panic pstore
reports and destroying ramoops nodes; console-ramoops-/dmesg-ramoops- strings
present. This is evidence of supported filter/cleanup functionality, NOT
runtime proof or control-flow proof that this boot's marker was deleted.
Exact cleanup conditions require code/disassembly. Do not fabricate a panic
phrase or induce panic merely to pass the filter. Root obtained after Android
boot may occur after panicreporter, so late post-root collection cannot alone
validate absence of previous console data.

## PMSG discriminator result
Before: 9653d9d1-799b-48dd-bd0c-de3c20a7309a
After: 5b9eb78c-0c06-4bbb-91d6-f2d2d289ad98
/dev/pmsg0 existed as character device; user's marker write returned 0.
Post-reboot archive valid; pstore.tar only '.', no pmsg/console/dmesg records.
Thus neither tested marker channel has demonstrated persistence through this
normal reboot + root restoration + late collection. The identified console/
dmesg-only crashreporter purge is insufficient to explain missing PMSG by itself.
Cannot choose between firmware RAM clearing, backend startup behavior, another
consumer, ring overwrite or an additional reboot from these late samples.
Stop repeating equivalent resets. No reliable syscore trace transport yet.
