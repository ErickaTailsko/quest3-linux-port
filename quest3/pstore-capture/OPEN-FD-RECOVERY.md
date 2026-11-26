# Existing open pstore FD recovery candidate

New files received: installed logcatd matches the AOSP wrapper, without an
explicit pmsg deletion command. State contains only logd.logpersistd.enable=true;
no selected logcatd property or service state was present in this capture.
This does not prove the daemon never ran. Directory listing is INVALID:
its full content is "error: closed", an ADB failure, not an empty directory.

Previously supplied expanded init rules show health service file directives
for /sys/fs/pstore/console-ramoops-0 and console-ramoops. Need full health rc
and live /proc/PID/fd links to learn whether the service holds either file.

Kernel source fs/pstore/inode.c pstore_unlink calls backend erase and
simple_unlink, but does not free its independent record->buf. That buffer is
freed by free_pstore_private called at inode eviction. pstore_file_read uses
record->buf, not ramoops backing memory. An existing open inode can therefore
outlive pathname removal. Backend erase frees old_log, a separate allocation.
This is a source-backed recovery candidate, not proof a file was opened on
this device, that the callback sequence ran, or that any marker survived reset.

A local Linux open/unlink/proc-fd reopen experiment verified generic VFS
behavior and independent file offsets. It does not substitute for target
pstore validation. Next device action is metadata only: full health rc and
open FD symlinks. No reboot, service changes, module or raw-memory access.

## Target result received

Full health rc distinguishes vendor.health-default from vendor.charger.
The normal boot handler starts vendor.health-default, which opens only
/dev/kmsg for writing. The console-ramoops and last_kmsg read directives are
under vendor.charger, started by on charger. They do not establish an open
console file in the normal Android boot tested here. No charger-mode action
is justified by this result.

Provided FD listing has 12,803 lines and no ramoops or /sys/fs/pstore target.
No existing handle was found to recover through this route. This is a
snapshot; proc entries may have changed or been inaccessible during collection.
No proof of firmware clearing vs early record removal follows from this absence.

Close existing-open-FD recovery for this normal boot. Do not repeat this scan
or equivalent marker reboots without a new capture mechanism. An observer
reboot test remains blocked by unvalidated persistent/early capture. Do not
claim logging infrastructure or CFI handoff is ready.
