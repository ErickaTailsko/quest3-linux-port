# Default-CMA identity query — host-only prototype

**ARM64 stock module built and artifact checks passed on the host. No live
transport is supplied, and nothing has been sent to the Quest.**
`controller.py` has `EXPECTED_MODULE = None` and refuses collection; its script
entry point always exits without performing operations. Tests arm only an
in-memory copy with a synthetic fixture hash and fake transport. The actual
module hash is recorded in build-verification.json, NOT enabled in the controller.
[Stock build result](../../docs/reports/2026-11-17-default-cma-identity-build.md).

## Scope

`q3_cma_identity.c` checks only `/reserved-memory/linux,cma`. It requires
`inspect`, a 32-character lowercase hex attempt token, the reviewed static OF
configuration and protection guards, and Quest 3/Anorak compatibility. It checks
the 32 MiB descriptor's properties/bounds and compares the non-null exported
default-area pointer with descriptor `priv` **before** calling typed
`cma_get_name`. It then reobserves pointer identity, not a lifetime pin.

A root-only immutable sysfs report records the attempt token, stage/error and
identity result. Reading the report does not repeat lookups. There are no payload
allocator calls, private CMA field reads, callbacks, PFN surveys, CPU pauses or
handoff. Loading any kernel module would still allocate normal metadata and
could crash; this is not a purely read-only device operation.

The backend-free controller accepts only an explicitly supplied test transport.
Each call requires a unique completion frame; raw stdout or local exit zero
alone is insufficient. transport_protocol.py supplies framing, not an adapter.
It verifies preflight hashes, creates a unique temporary path without clobbering,
checks transferred length/hash, persists insertion intent with fsync before the
single attempt, and validates strict bounded reports. It never retries insertion
or resumes an existing evidence directory. No executable ADB adapter is included.

Cleanup requires the same observed boot, absence before insertion, and a current
report with this attempt's token. Malformed/foreign reports, changed boot,
unexpected module appearance, uncertain file creation or failed removal stop
cleanup rather than trigger blind deletion/unload. Any timeout, missing/invalid
completion frame, transport interruption or journal durability failure latches a
stop: NO further automatic commands, including reads or cleanup. A remote action
may still be running. Only proven foreground completion allows subsequent steps;
a nonzero framed status is a known failure, not a reason to retry. Lost
removal replies remain incomplete, with no repeated removal. Serialized exclusive
use is still required; these checks are not an atomic lock against external
reboots or other module managers.

No accepted report proves free pages, active allocator bitmap, allocation
ownership, DMA safety or boot readiness. A new evidence path does not itself
grant permission for another attempt.

## Tests

```sh
python3 quest3/cma-identity-query/test-query.py
python3 quest3/cma-identity-query/test-controller.py
```

The first compiles actual query/init/exit/report bodies against host C mocks,
including error cleanup. It does not compile against ARM64 kernel headers or
validate stock ABI, CFI/LTO flags or module imports. The second uses only fake
transport, including uncertain transfer/insertion/removal, ownership collisions,
boot changes and malformed reports. Neither test contacts hardware. The separate
completed ARM64 build passed `tools/verify-cma-identity-module.py`: actual ELF
imports/__versions/stock CRCs, recorded protections and provenance were checked.
This does not prove complete stock binary equivalence or runtime lifetime safety.
The full host suite now has 60 passing tests, including synthetic ELF regressions,
completion framing, real host filesystem/lock/crash tests and a native C
supervisor tested only with local fixtures.

`receipt_store.py` is a **host reference, not a remote helper or dispatcher**.
It records immutable claims/results, pins directory/lease identities and keeps
unresolved claims blocking new nonces after a supervisor crash. It never executes
actions, cleans objects or authorizes resume. The current controller is NOT wired
to it; unknown transport completion still freezes that controller.
[Receipt/lease scope and limits](../../docs/reports/2026-11-17-cma-receipt-lease-reference.md).

`native-supervisor/` adds a C execution/receipt core with a disarmed default.
Only host-test builds dispatch fixtures. It waits/reaps before publishing and
uses a separate v2 receipt. Two disarmed ARM64/Bionic API28 artifacts now pass
offline checks, without Android execution or automatic ledger/controller
integration. [Native scope](native-supervisor/README.md).

An explicit host-only v2 catalogue observer now recovers matching native
receipts under pinned context and a held observation lease. It does not grant
admission, bootstrap, sequence verification, replay, cleanup or resume, and
does not migrate the old ledger or unfreeze the controller.
[Review and remaining bootstrap contract](../../docs/reports/2026-11-17-cma-v2-catalog-bootstrap-review.md).

A non-executable v3 draft now models fixed typed roles, receipt predecessor links
and explicit local checkpoints. Frozen synthetic vectors test canonical bytes;
rewritten unanchored tails are not authenticated and never authorize execution.
No native writer, ledger migration or controller integration was added.
[Draft/limits](../../docs/reports/2026-11-17-cma-v3-chain-draft.md).

A separate default-disarmed native bootstrap reference now publishes host fixture
metadata under a prior private-parent anchor. Every existing root blocks creation;
partial publication and lost replies never permit takeover or automatic retry.
Its observer proposes pins only, without import, activation or controller integration.
[Host bootstrap result/limits](../../docs/reports/2026-11-17-cma-native-bootstrap-host.md).

Separate ARM64/Bionic API28 bootstrap builds (minimal and core-retained) now pass
offline checks; both main functions remain write-only/return-77. No Android
execution, pin import, writer activation or controller integration was performed.
[Bootstrap Android build](../../docs/reports/2026-11-17-cma-bootstrap-android-build.md).

A separate host-fixture journal now tests local intent/ACK/explicit fixture-pin
import. Every error freezes the writer; restart observation never reconstructs
its live checkpoint. No production pin import, activation, transport or controller
integration is enabled. [Local ACK/limits](../../docs/reports/2026-11-17-cma-bootstrap-local-ack.md).

A pure bootstrap completion contract now checks the existing nonce/status frame,
exact reply/receipt and supplied wait/capture/boot context. Restart comparison
requires an independently caller-held anchor; it neither persists that anchor nor
authenticates history or permits writer recovery. No existing journal/controller
was integrated. [Completion contract](../../docs/reports/2026-11-17-cma-bootstrap-completion-contract.md).

The selected separate-witness direction now has a host-only SQLite/Ed25519
reference: immutable-per-store digest bindings, prior-key signature checks,
distinct publication/observation statements and explicit read-only restart.
It does not deploy a service, establish real isolation or prevent witness
rollback/equivocation. No controller admission is enabled.
[Witness result/limits](../../docs/reports/2026-11-17-cma-bootstrap-witness-host.md).

A supplied-byte witness audit now compares signed bindings against a caller-held
old digest and preserves portable conflict evidence. It detects presented forks,
not hidden histories; matching statements and duplicate signatures never prove
non-equivocation or authorize recovery. No witness/controller integration was added.
[Signed-conflict audit](../../docs/reports/2026-11-17-cma-witness-signed-conflict-audit.md).

A host-fixture client-policy wrapper now checks distinct prior keys, exact
digest/action scope and signed session/submission/response, claiming nonces
before delegation. It does not deploy an authenticated service, authenticate
policy origin, prevent rollback or enable controller admission.
[Client policy/limits](../../docs/reports/2026-11-17-cma-witness-client-policy-host.md).

The selected log + independent-monitor direction now has a bounded host model:
signed Merkle heads, old caller-held anchor, complete-prefix checks and binding
conflict rejection. It does not persist monitor state or prevent stale-anchor
forks; no service, network or controller integration exists.
[Log/monitor result](../../docs/reports/2026-11-17-cma-witness-log-monitor-host.md).

A one-lifetime host monitor store now commits a unique predecessor intent before
signing and atomically publishes checkpoint/head afterward. Errors freeze and
restart is inspection-only. It does not prevent rollback of both storage and
caller-held anchor or enable production recovery/controller integration.
[Store result/limits](../../docs/reports/2026-11-17-cma-monitor-anchor-store-host.md).

[Implementation record](../../docs/reports/2026-11-17-default-cma-identity-prototype.md)
and [scope/review plan](../../docs/reports/2026-11-17-default-cma-identity-plan.md).
The [transport/recovery review](../../docs/reports/2026-11-17-cma-transport-recovery-review.md)
found and corrected premature cleanup after unknown remote completion. Remaining
blockers: remote completion receipts/quiescence, exclusive lease/private paths,
and a separately reviewed ADB/su adapter. The stock host build and artifact checks
are complete, but live operation is NOT approved. Do not replace the disabled hash
or wire an adapter as a shortcut. Device authorization remains separate.
