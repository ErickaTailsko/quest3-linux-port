# CPU hotplug locking review

cpu_maps_update_begin/done are exported and lock cpu_add_remove_lock.
remove_cpu -> device_offline -> cpu_down -> cpu_maps_update_begin.
add_cpu -> device_online -> cpu_up -> cpu_maps_update_begin.
Holding the maps mutex across either API deadlocks (recursive mutex).
Holding cpus_read_lock across removal blocks the required write lock.
cpu_hotplug_disable makes our own add/remove return EBUSY as well.
pause_cpus drains scheduler activity, not a substitute for PSCI CPU off.

Implemented final checkpoint: after successful removals, acquire maps lock,
compare the actual mask with the expected mask, release lock before all
restoration attempts. No jump or device shutdown occurs in this window.
Tests assert remove/add are never called with maps lock held, validate a
concurrent online event immediately before the checkpoint, and balanced lock
release before rollback. 24 host scenarios passed; ARM64 build passed.

This protects the snapshot against standard CPU-map hotplug paths only.
It does not make the whole removal/restoration sequence atomic, prevent ABA
races, freeze Android or firmware, or validate architectural kexec entry.
Active module dispatch remains EOPNOTSUPP. No further device test requested.
