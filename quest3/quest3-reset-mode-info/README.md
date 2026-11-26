# Read-only reset mode snapshot

q3_reset_mode_info reads exported reboot_mode and panic_reboot_mode once at
module insertion, exposes copies as observed_mode and observed_panic_mode
read-only sysfs parameters, and logs their integers. It does not set the real
modes, register reset/notifier handlers, call SCM/PSCI, request reboot, map RAM
or alter CPU state. Parameters supplied at insertion are overwritten by the
actual snapshots before exposure. No force_warm_reboot private symbol is used.

Enum values in the reviewed kernel: -1 undefined, 0 cold, 1 warm, 2 hard,
3 soft, 4 gpio. A current snapshot does not prove the mode used by a previous
reset or by later callbacks. It does not establish warm-reset firmware support
or RAM retention. No warm reset test is included in this delivery.

Public source qcom_scm_do_restart selects its OEM power-reboot call only for
REBOOT_WARM (handler priority130). PSCI priority129 uses SYSTEM_RESET2 for
warm/soft only if firmware support was discovered; otherwise SYSTEM_RESET.
This is a hypothesis to examine, not evidence of the last actual reset chain.
The unrelated legacy msm-poweroff warm-force variable must not be substituted.

Stock running-kernel ABI 5.10.246-gd7102a837402; CFI, SCS and Full LTO retained;
binary exports/import checks passed. This small read-only module has not yet
been tested on the Quest. Source and build log are included.

Run from this directory (fish), after checking SHA256SUMS:
    python3 push-reset-info.py
    and adb shell "su -c 'insmod /data/local/tmp/q3_reset_mode_info.ko'"
    and adb shell "su -c 'grep -H . /sys/module/q3_reset_mode_info/parameters/observed*'"
    adb shell "su -c 'rmmod q3_reset_mode_info'"
    echo "rmmod: $status"

Uploader uses the already-tested idempotent 4KiB offset rewrite algorithm,
checks exact local/remote SHA256 and never loads modules or reboots by itself.
No changes to the existing quest_kexec or raw snapshot module are included.
Rebuild: q3make -j4 M="$PWD" modules
