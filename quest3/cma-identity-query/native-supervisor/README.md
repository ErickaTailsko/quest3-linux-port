# Native supervisor prototype — disarmed Android build, host-tested core

**Default executable is disarmed. ARM64/Bionic API28 artifacts now pass offline
checks; no Android executable or device operation has been run.** Exit 77 was
observed only on the host build and inspected in Android main disassembly.
This is a single-threaded C execution/receipt
core, not an enabled Android action dispatcher or an ADB adapter.

Only `Q3_SUPERVISOR_HOST_TEST` builds expose the fixture CLI. Tests supply an
open host ELF fixture, a durable claim from the Python reference, pinned root/
lease descriptors and synthetic intent. No shell, kernel-module syscall, reset,
timeout-kill or automatic cleanup is implemented. Do not ship the test build.

```sh
python3 quest3/cma-identity-query/native-supervisor/test-supervisor.py
python3 quest3/cma-identity-query/native-supervisor/test-android-verifier.py
python3 quest3/cma-identity-query/native-supervisor/test-v2-catalog.py
python3 quest3/cma-identity-query/native-supervisor/test-chain-v3.py
python3 quest3/cma-identity-query/native-supervisor/test-bootstrap.py
python3 quest3/cma-identity-query/native-supervisor/test-bootstrap-android-verifier.py
python3 quest3/cma-identity-query/native-supervisor/test-bootstrap-ack.py
python3 quest3/cma-identity-query/native-supervisor/test-bootstrap-completion.py
python3 quest3/cma-identity-query/native-supervisor/test-bootstrap-witness.py
python3 quest3/cma-identity-query/native-supervisor/test-witness-audit.py
python3 quest3/cma-identity-query/native-supervisor/test-witness-client-policy.py
python3 quest3/cma-identity-query/native-supervisor/test-witness-log-monitor.py
python3 quest3/cma-identity-query/native-supervisor/test-monitor-anchor-store.py
```

The core verifies canonical claim/owner bytes, hashes the opened fixture and
mode, forks once, preserves the lease in the child, closes unrelated child FDs,
uses `fexecve`, drains bounded stdout/stderr separately and waits for the exact
PID. EOF alone is not completion. The parent tolerates INT/TERM/HUP while waiting
without forwarding a kill; SIGKILL cannot release a surviving child's lease.
There is no internal action deadline or force-unlock.

After reap it writes an immutable, fsynced native receipt **before** replying.
Receipt v2 distinguishes normal exit, signal termination and failed exec, and
retains both streams with sizes/SHA-256. Overflow or publication failure leaves
the claim unresolved; no truncated success is issued. A broken client response
does not remove a receipt already published. Publication/test-signal hooks exist
only in the host-test build.

Important boundaries:

- `monitor_anchor_store.py` is a **one-lifetime HOST store**, not an operational
  monitor. It validates an unsigned extension, commits/fsyncs a unique predecessor
  intent BEFORE signing, then transactionally publishes checkpoint/head. Errors
  freeze; an existing root never permits writer reopen. Restart inspection is
  read-only and cannot recover delivery, import an anchor or recheck log entries.
  Restoring both storage and the caller's anchor remains undetected: independent
  latest-anchor protection is still required. Full suite: 60 passing host groups.
  [Store result/limits](../../../docs/reports/2026-11-17-cma-monitor-anchor-store-host.md).

- `witness_log_monitor.py` models the selected **log + independent monitor**
  direction with distinct keys, signed Merkle roots, caller-held prior checkpoint
  and a bounded complete-prefix scan. It rejects rewritten history and appended
  conflicting bindings, but never fetches/persists entries or anchors. Supplying
  a stale genesis can still produce a second signed branch: latest-anchor
  provenance/storage and deployment isolation remain unresolved. Signature-only
  checkpoint review explicitly does NOT recheck the full prefix. The full suite
  at that stage passed 59 host groups. [Log/monitor limits](../../../docs/reports/2026-11-17-cma-witness-log-monitor-host.md).

- `witness_client_policy.py` is a **host-fixture wrapper**, not a network service.
  It checks a distinct prior client key and exact digest/action scope, signed
  session/submission/response, and in-memory nonce claims before delegation.
  Errors freeze both gate and witness handle. Raw FixtureWitness is still a
  low-level test API, not an authenticated endpoint. Policy provenance,
  deployment isolation and durable anti-replay/rollback remain unverified;
  deliberately reusing a test session nonce can recreate an old challenge.
  That client-policy stage passed 58 host groups.
  [Client policy/limits](../../../docs/reports/2026-11-17-cma-witness-client-policy-host.md).

- `witness_audit.py` verifies supplied signed statements against a caller-held
  old binding digest, and builds portable two-signature conflict evidence. It
  detects PRESENTED conflicting bindings, not hidden forks or rollback in
  general. Matching observations never establish safety, and duplicate signatures
  are not independent votes. It performs no I/O or writer recovery; every result
  requires remaining frozen. That audit stage passed 57 host groups.
  [Signed-conflict audit/limits](../../../docs/reports/2026-11-17-cma-witness-signed-conflict-audit.md).

- `bootstrap_witness_reference.py` is a **host-fixture witness**, not a deployed
  service. It tests SQLite FULL transactions and Ed25519 statements under a
  previously pinned public key. Publication and later observation are distinct;
  restart opens only a read-only observer. Same-host fixtures do NOT establish
  trust-domain separation, rollback protection or non-equivocation. No production
  key, client policy, network, service or controller integration exists. Tests
  require the already-installed Python `cryptography` package. The complete suite
  at that stage passed 56 host groups. [Witness result/limits](../../../docs/reports/2026-11-17-cma-bootstrap-witness-host.md).

- `bootstrap_completion_draft.py` is a pure completion/restart **contract model**.
  It checks the existing nonce/status frame against exact bootstrap reply/receipt,
  supplied wait/stream/boot context and an independently caller-held checkpoint.
  It does not authenticate those observations, persist an external anchor or
  recover a writer. Matching bytes never authorize resume/import/activation.
  That contract stage passed 55 host groups.
  [Completion contract/limits](../../../docs/reports/2026-11-17-cma-bootstrap-completion-contract.md).

- `bootstrap_ack_reference.py` is a separate **host-fixture filesystem journal**:
  intent, local ACK and explicit fixture-pin import are separate immutable
  publications. Only a checkpoint returned to the same live writer can advance
  it; every error freezes it, and read-only restart observation never recovers a
  writer/checkpoint. Fixture completion is NOT production transport validation.
  All real pin-import/admission/activation flags remain false. The full host
  suite at that stage passed 54 groups. [Local ACK result/limits](../../../docs/reports/2026-11-17-cma-bootstrap-local-ack.md).

- `bootstrap.c` is a separate **metadata-only host reference**, default disarmed.
  Its host-test CLI exclusively creates a fixed root under a previously pinned
  private parent, retains partial publication and refuses every existing root.
  `bootstrap_receipt.py` only proposes observed pins; it never imports them,
  acknowledges a local journal or activates a writer. Separate API28 disarmed
  and retained-core Android builds now pass offline checks; neither was executed.
  Runtime validation remains absent. The bootstrap Android build stage passed 53
  host groups. [Host result](../../../docs/reports/2026-11-17-cma-native-bootstrap-host.md),
  [Android build/limits](../../../docs/reports/2026-11-17-cma-bootstrap-android-build.md).

- The prototype requires a precreated claim and accepts only one operation per
  directory. It does not implement the native catalogue, initialization, lease
  retirement, production command policy or current-device/boot verification.
- The host fixture fingerprint is not a production action ABI.
- Native receipt v2 is deliberately incompatible with the schema-v1 reference
  ledger. Neither parser/controller silently migrates or resumes it.
- `v2_catalog.py` is an explicit **host-only observer**, not an admission API.
  It checks prior pins, two injected boot samples, canonical owner/claims and
  native receipts while holding its own lease. It never creates/migrates stores,
  changes the controller journal or permits replay, cleanup or resume. Receipts
  v2 do not encode historical sequence; a matching catalogue is not a completed
  transaction. [Bootstrap/catalogue review](../../../docs/reports/2026-11-17-cma-v2-catalog-bootstrap-review.md).
- `chain_v3_draft.py` is a pure **non-executable contract model**, not a native
  writer/dispatcher. It binds fixed typed roles, ordinals, per-command nonces,
  predecessor receipts and caller-held local checkpoints. Hashes are NOT
  authentication or historical execution proof. Unanchored tails remain
  untrusted, and all execution/authorization/resume/cleanup flags remain false.
  `v3-draft-vectors.json` contains synthetic frozen vectors, not a real device
  plan or permission. [v3 draft](../../../docs/reports/2026-11-17-cma-v3-chain-draft.md).
- `native_receipt.py` parses bytes, not filesystem/lease state. A valid receipt
  never sets safe_to_mutate, automatic_resume_allowed, lease_free_verified,
  tree_quiescence_proven or boot_ready.
- Parent directories and the caller/supervisor environment must be trusted;
  hashes and inode checks do not authenticate another root or prevent all races.
- Host GCC/PIE/LTO/stack-protector/RELRO checks are not Android CFI/SCS validation.
  The existing kernel/module candidates and their protections are unchanged.

Tests cover real host fork/wait, early stream EOF, signals, exec failure, lost
response, SIGKILL with an inherited lease, duplicate rejection, binary output,
output overflow, publication faults and SHA-256 against Python hashlib. No
test executes insmod/rmmod, a shell action or any operation on the Quest.

[Result and remaining gates](../../../docs/reports/2026-11-17-cma-native-supervisor-host.md).
Host compiler/artifact hashes: host-build-verification.json. Android hashes and
checks: android-build-verification.json; see the
[disarmed Bionic build result](../../../docs/reports/2026-11-17-cma-native-android-build.md).
The official
[NDK r30 is now prepared locally](../../../docs/reports/2026-11-17-android-ndk-r30-preparation.md),
and the first Bionic build is complete, but device ABI/runtime, filesystem/SELinux,
production dispatcher, native catalogue/schema integration, reconciliation and
explicit authorization remain pending. The controller's
approved module hash remains disabled.
