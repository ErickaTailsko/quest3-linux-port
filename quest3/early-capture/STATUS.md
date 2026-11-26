# Early pstore capture readiness

Singularity public repo examined at d5e372299882947079d2f8ad778a3bde3fad6530.
Checkout has README, assets and Frida binary; no application source, manifest,
BootReceiver or boot script. README advertises root-on-boot and says successful
root triggers a soft reboot; that does not establish pre-boot-completed root.

Device init starts panicreporter on sys.boot_completed=1. Its library has a
verified non-panic drop and purge path. An Android BOOT_COMPLETED receiver cannot
be treated as earlier than that init trigger; no guaranteed ordering exists.
LOCKED_BOOT_COMPLETED/directBootAware alone would not prove root before this
trigger either. Need actual installed manifest/receiver information and timing.
No /data/adb boot scripts installed; no service disabled; no reboot requested.

Decision: do not propose Magisk post-fs-data hooks as proven early hooks with
exploit-based root. Scripts run by late Magisk injection might be too late.
Next read-only evidence: dumpsys package com.lumi.singularity and current
panicreporter state, to establish available events and installed variant.
If only late boot receivers are available, early capture needs another mechanism
or a separately justified change to collector startup; don't repeat identical
marker reboots or assert RAM loss from the empty late pstore.

## Installed package evidence
Singularity 1.0.8 versionCode50 registers .system.BootReceiver for
android.intent.action.BOOT_COMPLETED, priority1000. No LOCKED_BOOT_COMPLETED
receiver appears in supplied resolver table. Receiver priority only orders
Android broadcasts; it cannot order against init's sys.boot_completed trigger.
This package evidence does not establish an early root path. panicreporter
state stopped with sys.boot_completed=1 is consistent with oneshot completion,
but does not prove execution, successful purge or absence of earlier failures.
Library strings identify concrete fallback config path:
/system_ext/etc/ovr_crashreporter.conf. Read it before proposing any supported
capture or preservation configuration. Do not rewrite config or set unknown keys.

## Supplied fallback configuration reviewed
Valid JSON ovr_crashreporter.conf sets pstore directory /sys/fs/pstore and
report directory /data/misc/crashes/. Other entries concern app/upload/UUID
and error metadata. No preserve-non-panic or disable-purge entry is present.
Do not infer arbitrary undocumented options from absence in this file.
Changing report directory would not bypass the confirmed non-panic filter.
Changing pstore directory would divert/disable collection, not capture it;
with late exploit root it is not demonstrated to apply before boot collector.

Decision: supported-configuration route has no demonstrated solution. Existing
late ADB/pstore collection cannot validate retention, and no early-root hook
is established. Stop identical reboot trials. Syscore active transition remains
blocked; passive callback observation still needs a reliable post-reset record
or external trace. No device configuration changed.
