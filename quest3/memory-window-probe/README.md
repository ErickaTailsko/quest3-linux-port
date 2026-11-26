# Pageblock metadata probe — prototype, NOT deployable on current stock

This is a source prototype, tested with host mocks only. No kernel .ko was
built or loaded in this step. It deliberately refuses CONFIG_MEMORY_HOTPLUG,
which is enabled in the observed Quest 3 stock configuration.

## Why it refuses

Safe PFN/page/zone traversal needs an established metadata lifetime contract.
Stock enables memory hotplug/hot-remove; the supplied Module.symvers does not
export get_online_mems/put_online_mems. Checking pfn_valid before a dereference
alone does not establish serialization against teardown. No equivalent exported
protection has been demonstrated. A memory notifier is not automatically a
replacement: an offline operation might already be in flight when registered.

Do not remove this guard, resolve private lock addresses, disable stock hotplug,
or treat an idle-looking device as proof of serialization. This is a conservative
implementation limitation, not proof that all possible RO designs are impossible.

## Prototype behavior

- Fixed window [0x90000000,0x93400000), 4 KiB pages, order-10 pageblocks.
- Requires both Eureka and Anorak compatibility; no arbitrary-address parameter.
- Refuses hotplug before touching PFN/page metadata.
- On a supported configuration, validates every PFN/non-device page, samples
  per-block zone, migration type before/after and reserved-page counts.
- Report is root-readable under module parameters and immutable after init.
  An insertion-time `report` argument is ignored/overwritten; it cannot change
  the window or influence an allocation.
- Never allocates, frees, isolates or migrates pages in the window. No SCM,
  MMIO, CPU hotplug, notifier registration, reboot or transition operation.

Even if migration types match before/after, the sample is not atomic. Reports
never declare allocation feasibility, ownership or DMA safety.

## Tests and build limits

```sh
python3 quest3/memory-window-probe/test-probe.py
```

The test compiles the actual C source against host stubs. It checks hotplug and
board rejection before PFN access, invalid/device PFNs, uniform/mixed zones and
types, reserved pages and lack of an ownership claim. Host tests exercise the
non-hotplug branch only as a simulation, not as evidence for this stock kernel.

No device load command is provided. Any future kernel build must use matching
stock headers/config/provided CRCs, preserve CFI/SCS/LTO and record provenance.
The QMP target build is not a substitute for stock module compatibility. Build
success would not resolve the lifetime guard or authorize deployment.
