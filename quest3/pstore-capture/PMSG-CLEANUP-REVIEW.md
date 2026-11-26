# Additional PMSG cleanup mechanism — source evidence, not target runtime proof

AOSP Android 14 tag android-14.0.0_r1, system/logging/logcat/logcat.cpp:
https://android.googlesource.com/platform/system/logging/+/refs/tags/android-14.0.0_r1/logcat/logcat.cpp
SHA256: c025cb5228b0134649e623b0420f5490e53f1a4e389b9d7f58519e5689197fc5

Lines 653-659: -c sets clearLog; -L selects ANDROID_LOG_PSTORE.
Lines 885-894: when both are set, unlink /sys/fs/pstore/pmsg-ramoops-0.
-L without -c does not enter that unlink branch.
This establishes an alternative PMSG consumer/eraser to investigate. It is not
proof that the installed vendor logcat is identical, that this command runs at
boot, or that any previous marker actually survived firmware reset.

Kernel source: ramoops_init_prz uses PRZ_FLAG_ZAP_OLD for console and pmsg;
persistent_ram_post_init first snapshots valid retained data into old_log,
then zaps the current persistent buffer. Reading that backing buffer late in
boot is not equivalent to reading the previous boot's exported pstore record.
ramoops_pstore_erase frees old_log and zaps the corresponding buffer for PMSG.
Therefore a late raw-memory snapshot would not distinguish startup rollover,
record deletion and loss of retention. No raw mapping module is justified yet.

Next evidence: target init rules mentioning logcat/logpersist in addition to
literal pstore/pmsg, and target logcat help. Existing literal pstore-only search
could miss a logcat -L -c invocation. Do not run clear options, alter services,
fake panic strings, or repeat a reboot to obtain this evidence.

## Target init and help received

Expanded init search confirms /system/etc/init/logcatd.rc line 55 configures
/system/bin/logcatd -L ... -f /data/misc/logd/logcat ... --id=${ro.build.id}.
Service start is conditional on logpersist properties. This configuration is
not evidence that logcatd ran during the test. Line 42 uses logcat -c -f for
rotated files, without -L; it is not the identified pmsg unlink command.
-D in line 55 means dividers, as confirmed by target logcat help, not deletion.
No explicit combined -L -c command was found in the supplied init matches.
This does not exclude commands constructed by scripts or other consumers.

The AOSP Android 14 logcatd.sh source reads prior logs via the supplied -L
arguments, then execs logcat without -L. No explicit pmsg clear is present.
The installed /system/bin/logcatd must be checked; do not assume vendor parity.
If enabled, /data/misc/logd may hold a text copy of parseable Android pmsg logs.
A raw ASCII write to /dev/pmsg0 is not necessarily a valid Android logger
record, so absence of that marker in decoded logcat text is inconclusive.

Next read-only evidence: installed logcatd script plus full service config,
logpersist service/property state, and /data/misc/logd listing. No service
start/stop/property changes or reboot required. Retention remains unvalidated.
