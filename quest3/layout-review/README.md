# Offline layout review

`returned_layout.py` validates **host-fixture** Image/initrd/DT slots supplied as
separate allocation-result records. It does not allocate, prove ownership, select
a device base, copy payloads, free memory or integrate/activate the loader.

It checks ARM64 header/effective-size/page arithmetic, the Image/initrd window,
complete-slot non-overlap, supplied DT RAM/static exclusions and conservative
2 MiB ancillary slots. Dynamic reservation locations and current memory ownership
remain unverified. Optional `prepare_dtb` returns new bytes changing only chosen
initrd-address semantics; it never writes a file.

```sh
python3 quest3/layout-review/test-returned-layout.py
python3 quest3/layout-review/test-returned-layout-core.py
python3 quest3/layout-review/test-relocation-plan.py
python3 quest3/layout-review/test-staging-comparison.py
python3 quest3/layout-review/test-direct-staging-trace.py
python3 quest3/layout-review/test-cache-publication-plan.py
python3 quest3/layout-review/test-staging-binding-review.py
python3 quest3/layout-review/test-cache-leaf-static-review.py
python3 quest3/layout-review/test-cache-leaf-import-review.py
```

Tests deliberately use fictitious 64 GiB addresses/RAM, NOT proposed Quest bases.
Real trim3/initrd measurements are checked without making them boot-ready.
The captured stock DT and USB boot-candidate DT remain distinct, unchanged inputs.

`check-layout.py` and `fdtcheck.py` retain the older fixed-address review tools;
passing either layout checker does not reserve RAM or permit handoff. The actual
loader still uses fixed destinations and is unchanged by this host reference.

`returned-layout-core.h` adds a separate arithmetic-only C reference, not included
by the loader. Host/UBSan tests compare 2,000 seeded cases with Python and check
full-allocation intersection masks for source/descriptor/code/page-table/scratch
ranges. A zero mask is NOT proof of usable RAM; errors leave outputs untouched.
The C core does not parse Image/DT bytes, check IDs/attempt or prove ownership.
Its Linux branch/target ABI and loader integration remain unvalidated.

[C core result and remaining gates](../../docs/reports/2026-11-18-returned-layout-c-core-host.md).

`relocation_plan.py` models immutable source snapshots, separate work-page
records and 255-entry linked descriptor pages in host bytes only. It rejects
work/destination aliases and validates file/tail/BSS snapshots and descriptor
corruption. Retained metadata equality is NOT proof of actual page lifetime.
No code/page tables are built and no physical pointer is followed.

The larger fixture accounts for 36 MiB of destinations PLUS about 32.63 MiB
of sources/descriptors/auxiliary pages, before other costs. The full suite now
passes 63 host groups; no allocator/loader/handoff is enabled.
[Staging model and budget](../../docs/reports/2026-11-18-relocation-staging-plan-host.md).

`staging_comparison.py` compares that retained-resource baseline with a hypothetical
bounded-stream direct route using identical destinations and assumed equal
transition/scratch budgets. The large fixture accounts for 68.63 versus 36.02 MiB
with a 4 KiB buffer, NOT measured peak memory. Image CMA remains 32 MiB. No writer,
streaming implementation, no-copy trampoline or runtime route selector exists.
The full suite passes 64 host groups; all ownership/execution gates stay false.
[Comparison, ordering and failure limits](../../docs/reports/2026-11-18-staging-comparison-host.md).

[Direct staging contract review](../../docs/reports/2026-11-18-direct-staging-contract-review.md)
specifies real-handle retention, mapping/isolation, bounded I/O, byte sealing,
separate PoC visibility and fail-closed uncertainty. This is a document, not a
writer, new runtime gate or extra test group. Next: host-only phase/failure traces.

`direct_staging_trace.py` now checks HOST-only event claims for single-buffer
short reads/copy/zero progress, sealing, irreversible boundary and final clean.
Failures/uncertainty terminate the trace and forbid later commands. It has no
reader/writer, callbacks, physical addresses or real handles; even a complete
entry description leaves ownership/authorization/cache/boot_ready false.
The suite now passes 65 host groups.
[Trace semantics and regressions](../../docs/reports/2026-11-18-direct-staging-traces-host.md).

[Stock source/ABI review](../../docs/reports/2026-11-18-direct-staging-stock-abi-review.md)
cross-checks real prototypes/exports and mapping/cache semantics offline. CMA/buddy
pairs are exported, but internal PoC helpers are absent from the supplied export
table; exported `flush_dcache_page` only updates a flag here. No adapter, writer,
new build/test group or runtime gate is added. Next: cache publication options
and the actual irreversible boundary, host-only.

[Cache publication/boundary review](../../docs/reports/2026-11-18-cache-publication-boundary-review.md)
compares publication options and separates observer freeze, USB loss, optional
non-invertible secure-watchdog mutation and global shutdown. The legacy abort
label is not proof of complete rollback. No helper, adapter or runtime path is
approved; the existing trace boundary must not be equated with PHASE 11.

`cache_publication_plan.py` separately reviews synthetic byte/line intervals for
payloads, code and PGD/PUD. Later writes dirty the affected D-cache lines; code
writes also invalidate its I-cache claims. A coverage checkpoint is NOT a seal
or runtime admission. Independent observation/irreversibility markers and terminal
uncertainty are tracked, without cache ops or a helper. It does not relax the
phase trace's no-write-after-seal rule. The suite now passes 66 host groups.
[Range coverage, last writes and limits](../../docs/reports/2026-11-18-cache-publication-ranges-host.md).

`staging_binding_review.py` composes these HOST models on one ordered timeline.
Payload resources must match the layout exactly; payload write intervals are
derived only from phase copy/zero completions. Code/tables must be initialized
before seal; coverage is checked at final-clean. No runtime admission or helper
is enabled. The suite passes 67 groups, including real trim3/initrd with synthetic
DT/resources and a declared 64 KiB buffer. Full trim3/4 KiB traces exceed this
composition's 2,048-step limit and were NOT validated by it.
[Bound fixture review and remaining gates](../../docs/reports/2026-11-18-staging-binding-host.md).

[Lifetime/helper ABI evidence review](../../docs/reports/2026-11-18-lifetime-helper-abi-evidence-review.md)
separates static pool descriptors from real allocation/mapping lifetime. It also
inspects existing direct-call leaf code without approving a new CFI target or
helper. Holding a memory-hotplug read lock through CPU shutdown is not a generic
lifetime solution. No build, added test group or runtime gate; 67 groups remain.

[Local leaf acceptance contract](../../docs/reports/2026-11-18-cache-leaf-acceptance-contract.md)
defines L01–L14 and future negative controls for direct-call ABI, CFI/SCS/BTI/PAC,
ranges and separate cache/lifetime obligations. No helper or verifier is added;
specified test vectors are NOT newly executed tests. Next: a read-only static
verifier, with missing evidence kept PENDING and runtime admission disabled.

`cache_leaf_static_review.py` now implements a read-only subset: bounded AArch64
REL ELF/relocation parsing, narrow BTI/register/PAC CFG review and separate uint64
range arithmetic. It never executes inspected words. Overall output is ALWAYS
PENDING or REJECT (CLI exit 2/1, no approval exit 0). Historical ELF is a negative
PAC control; synthetic positive ABI subchecks still do not approve a helper.
Source provenance, caller ABI/CFI, platform PoC and lifetime remain PENDING.
The suite now passes 68 host groups.
[Static verifier scope and negative controls](../../docs/reports/2026-11-19-cache-leaf-static-verifier-host.md).

The parser now caches bounded name scans and uses a caller-query sweep rather
than scanning all symbols per reference; 10,000 query cases preserve ambiguity.
A one-off historical artifact audit matches 72 version records/CRCs and the
declared VFS namespace; SCM imports depend on modular qcom-scm. This is local
content/interface consistency, NOT build provenance or caller ABI proof. No
generic provenance verifier or helper was added; the suite remains 68 groups.
[Parser limits and caller/import evidence](../../docs/reports/2026-11-19-cache-leaf-parser-caller-evidence-review.md).

`cache_leaf_import_review.py` checks bytes/records only: exact version/undefined
sets, stock CRC/provider/kind/namespace, declared license/dependencies, explicit
immutable import rules and optional content pins. No policy is inferred from ELF.
Even completely consistent replacement bundles stay globally PENDING; build,
caller ABI/CFI, cache and lifetime are not established. This API does not replace
the separate leaf/PAC review. The suite now passes 69 groups; no helper/build/
loader or device path was added.
[Import-policy checks and negative controls](../../docs/reports/2026-11-19-cache-leaf-import-policy-host.md).

[Isolated candidate build/evidence plan](../../docs/reports/2026-11-19-cache-leaf-isolated-build-plan.md)
specifies future stock inputs, fresh O=/M= directories, refusal-only init, caller
retention under Full LTO and gates B0–B5. No candidate source, build directory,
helper or build was created/run. Next: review the inert caller/source proposal
before implementation; no loader or device path is authorized.

[Result, provenance and remaining C/allocator gates](../../docs/reports/2026-11-18-returned-allocation-layout-host.md).
