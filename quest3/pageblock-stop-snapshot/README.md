# Experimental pageblock head snapshot using stop_machine

**Update: one consented device sample completed, report collected and cleanup
confirmed.** See device-sample-result.json and the project device-result report.
This is not universal hardware/lifetime validation. The build-verification.json
records the earlier build-only stage. This is an
alternative to the blocked plain metadata traversal in memory-window-probe.
It reads metadata but is NOT operationally passive: it pauses the system.
Explicit user consent is required for a device experiment.

## Contract and limits

- Disabled by default: insertion without explicit sample opt-in returns EACCES
  before calling stop_machine. No address or duration parameters are accepted.
- Fixed 13 pageblock heads, 4 MiB apart, in [0x90000000,0x93400000).
- Uses the exported typed stop_machine API with one callback CPU. Reviewed
  source stops other online CPUs with IRQs disabled while the callback runs.
- Callback uses pfn_to_online_page, rejects missing/device pages, and copies
  migration type, zone name and PageReserved of each HEAD into preallocated data.
- No allocation, sleeping, sysfs, printk, formatting or migration in callback.
- A 1 ms callback budget is checked between heads and at completion. It is
  **not a bound on total system pause/rendezvous**, watchdog response or latency.
- Formatting and root-readable sysfs report publication occur after CPUs resume.
- Failure does not publish a partial successful report. No reset is requested.

The source-level synchronization argument is that memory teardown tasks cannot
advance during the stopped-CPU callback, and online-section/PFN checks reject
offline metadata. That argument still needs review against actual vendor
behavior; no runtime proof or universal firmware/DMA safety is claimed.

Only heads are sampled, not all 13,312 PFNs. Uniform head observations do not
prove valid/reservable pages throughout the window. They do not provide page
ownership, stop DMA, turn CMA into free memory, or validate a kernel handoff.

## Build provenance

Full kernel/module build tools were prepared in `.work/stock-probe-out/` using
the supplied stock `.config` unchanged. The existing stock Module.symvers was
copied explicitly; modules_prepare did NOT generate a replacement CRC table.
Source is the pinned public kernel revision, with only the documented host
OpenSSL compatibility patch. External sources were copied to
`.work/pageblock-probe-src/` so generated files do not pollute public sources.

Result: stock release vermagic, 21 versioned imports matching the supplied table,
CFI entry present and CFI/SCS/LTO/x18 flags recorded. This does not demonstrate
complete binary equivalence to the vendor kernel. See build-verification.json.
The `.ko` and logs are retained in the ignored project directory
`private-diagnostics/pageblock-stop-snapshot-prepared/`, not published here.

## Host test

```sh
python3 quest3/pageblock-stop-snapshot/test-callback.py
```

Compiles the production callback with MMIO-free metadata/clock mocks. Checks
IRQ context, fixed heads, offline/device rejection, partial failure, budget and
a callback-call whitelist. It does not pause CPUs or prove lifetime protection
on a real machine. It is included in the main host suite.

## Device experiment protocol — executed once, do not repeat implicitly

After explicit consent: preserve evidence; verify root, release, boot ID, module
absence and hashes; send a unique temporary module file; attempt insertion only
once with the sample opt-in. Collect `/sys/kernel/q3_pageblock_snapshot/report`,
verify 13 exact head addresses and metadata format, remove the module, verify
sysfs/module absence, delete the temporary and confirm the same boot.

Do not retry an uncertain insertion/response. Do not reset or start Singularity
as automatic recovery. Stop if root/ADB changes or cleanup is uncertain. Even a
successful sample does not authorize alloc_contig_range or handoff.

`collect-once.py` implements that protocol and requires --ack-system-pause.
`test-controller.py` uses fake ADB only. No new execution is implied by the
presence of this script or the successful sample already recorded.
