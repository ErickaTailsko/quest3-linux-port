# Fixed-list reserved-memory descriptor query

**The one authorized query completed: 13 descriptor locations obtained and
module/sysfs/temporary-file cleanup confirmed in the same boot. Do not reload
automatically; the one-insertion authorization has been consumed.**
[Device result and limits](../../docs/reports/2026-11-17-reserved-descriptor-result.md).
The earlier failed upload had zero insertions; its temporary path was confirmed
absent after reconnection. That failure remains preserved as historical evidence.

## Scope

- Default disarmed; `inspect=1` opts in to one lookup of each of 13 fixed nodes.
- Uses exported typed OF APIs. No kallsyms, kprobe, PFN sampling, content reads,
  CMA allocation, callback invocation, CPU pause, reset or handoff.
- Copies only base, size and ops/priv presence into a static report. Reading the
  root-only sysfs report does not perform new lookups.
- Checks expected node names, DT pool properties, descriptor sizes, alignment,
  alloc-range bounds and overlap. Failed descriptors remain errors, not locations.
- Public-header struct layout assertions and stock CRC checks are not proof of
  complete stock binary equivalence or DMA safety. Kernel module load can crash.

`collect-once.py` pins the reviewed module, runtime configuration and captured
DT hashes. It requires explicit acknowledgement, persists insertion intent,
never retries insertion and verifies module/temporary-file cleanup in the same
boot. The initial `adb push` transport failed; the revised uploader uses unique
temporary files and fixed-offset 4 KiB chunks, with byte count and SHA-256
verification before insertion. This revised transfer passed in the authorized
device operation, with one insertion and verified cleanup.
Neither lost replies nor exit zero alone establish transfer/action success.

## Host verification

```sh
python3 quest3/reserved-descriptor-query/test-query.py
python3 quest3/reserved-descriptor-query/test-controller.py
```

Tests compile the actual C query/validation bodies against mocks and exercise
the controller with fake ADB, including a lost chunk response, lost insertion
response, changed boot, preexisting module and partial cleanup. They do not
prove runtime ABI, lifetime or firmware behavior; the separate device result
records the actual authorized query.

Build was performed in `.work/reserved-descriptor-src/` with the previously
prepared `.work/stock-probe-out/`, Clang r450784e and supplied stock symvers:

```sh
Q3_OUT="$PWD/.work/stock-probe-out" tools/q3make -j2 \
  M="$PWD/.work/reserved-descriptor-src" modules
```

That command assumes matching sources/headers have already been prepared;
do not copy in a QMP/trim candidate config or regenerate different CRCs. Local
binary and compile command are archived under ignored private diagnostics.
Reviewed build metadata is in `build-verification.json`. No automatic module
deployment is part of a build or host test.
