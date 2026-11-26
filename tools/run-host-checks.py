#!/usr/bin/env python3
"""Run host-only regression models; no real ADB or kernel module operations."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
q = repo / 'quest3'
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--report', type=Path, default=repo / 'test-results.json')
args = ap.parse_args()
tests = [
    '../tools/test-startup-timeline.py',
    '../tools/test-qmp-candidate.py',
    '../tools/test-cma-identity-module.py',
    '../tools/test-handoff-exports.py',
    '../tools/test-memory-window.py',
    '../tools/test-memory-survey.py',
    '../tools/test-section-coverage.py',
    '../tools/test-stock-allocation.py',
    '../tools/test-memory-map-collector.py',
    '../tools/test-payload-geometry.py',
    'memory-window-probe/test-probe.py',
    'pageblock-stop-snapshot/test-callback.py',
    'pageblock-stop-snapshot/test-controller.py',
    'reserved-descriptor-query/test-query.py',
    'reserved-descriptor-query/test-controller.py',
    'cma-identity-query/test-query.py',
    'cma-identity-query/test-controller.py',
    'cma-identity-query/test-transport.py',
    'cma-identity-query/test-receipts.py',
    'cma-identity-query/native-supervisor/test-supervisor.py',
    'cma-identity-query/native-supervisor/test-android-verifier.py',
    'cma-identity-query/native-supervisor/test-v2-catalog.py',
    'cma-identity-query/native-supervisor/test-chain-v3.py',
    'cma-identity-query/native-supervisor/test-bootstrap.py',
    'cma-identity-query/native-supervisor/test-bootstrap-android-verifier.py',
    'cma-identity-query/native-supervisor/test-bootstrap-ack.py',
    'cma-identity-query/native-supervisor/test-bootstrap-completion.py',
    'cma-identity-query/native-supervisor/test-bootstrap-witness.py',
    'cma-identity-query/native-supervisor/test-witness-audit.py',
    'cma-identity-query/native-supervisor/test-witness-client-policy.py',
    'cma-identity-query/native-supervisor/test-witness-log-monitor.py',
    'cma-identity-query/native-supervisor/test-monitor-anchor-store.py',
    'layout-review/test-bootargs.py',
    'layout-review/test-returned-layout.py',
    'layout-review/test-returned-layout-core.py',
    'layout-review/test-relocation-plan.py',
    'layout-review/test-staging-comparison.py',
    'layout-review/test-direct-staging-trace.py',
    'layout-review/test-cache-publication-plan.py',
    'layout-review/test-staging-binding-review.py',
    'layout-review/test-cache-leaf-static-review.py',
    'layout-review/test-cache-leaf-import-review.py',
    'tests/collect-readonly-test.py', 'tests/cpu-flow-test.py',
    'tests/layout-host-test.py', 'tests/platform-host-test.py',
    'tests/preflight-dispatch-test.py', 'tests/scm-control-order-test.py',
    'tests/scm-host-test.py', 'usb-minimal/test-init.py',
    'usb-minimal/test-usb-role.py', 'handoff-observer/test.py',
    'cpu-hotplug-probe/test.py', 'cpu-multi-probe/test.py',
    'syscore-probe/test.py', 'restart-backend-design/phase_model.py',
    'restart-backend-design/test-memory-lifetime.py',
    'restart-backend-design/allocation_ownership_model.py',
    'restart-backend-design/test-cma-identity.py',
    'restart-backend-design/test-mem-buf-ranges.py',
    'ramoops-snapshot/test-copy.py', 'ramoops-snapshot/test-tools.py',
    'ramoops-snapshot/test-pmsg-stage.py', 'ramoops-snapshot/test-pmsg-compare.py',
    'warm-reset-guard/test-state.py', 'warm-reset-guard/test-cycle.py',
    'warm-reset-guard/test-request.py',
]
results = []
for name in tests:
    start = time.monotonic()
    completed = subprocess.run([sys.executable, str(q / name)], capture_output=True, text=True, timeout=120)
    results.append({'test': name, 'status': 'pass' if completed.returncode == 0 else 'fail',
                    'seconds': round(time.monotonic() - start, 3),
                    'stdout': completed.stdout, 'stderr': completed.stderr})
    print(results[-1]['status'].upper(), name, flush=True)
    if completed.returncode:
        print(completed.stderr or completed.stdout, flush=True)
llvm = os.environ.get('Q3_LLVM')
if not llvm:
    nm = shutil.which('llvm-nm')
    if nm and (Path(nm).parent / 'llvm-objdump').is_file():
        llvm = str(Path(nm).parent)
objdump = os.environ.get('Q3_OBJDUMP') or shutil.which('llvm-objdump')
for name, enabled in [('tests/x18-frame-test.py', bool(objdump)), ('verify-cfi-guards.py', bool(llvm))]:
    if not enabled:
        results.append({'test': name, 'status': 'skip', 'reason': 'external LLVM not configured'})
        print('SKIP', name)
        continue
    env = os.environ.copy()
    if llvm:
        env['Q3_LLVM'] = llvm
    if objdump:
        env['Q3_OBJDUMP'] = objdump
    completed = subprocess.run([sys.executable, str(q / name)], env=env,
                               capture_output=True, text=True, timeout=120)
    results.append({'test': name, 'status': 'pass' if completed.returncode == 0 else 'fail',
                    'stdout': completed.stdout, 'stderr': completed.stderr})
    print(results[-1]['status'].upper(), name, flush=True)
    if completed.returncode:
        print(completed.stderr or completed.stdout)
report = {'scope': 'host models/compiled source checks only; no hardware or boot validation',
          'passed': sum(r['status'] == 'pass' for r in results),
          'failed': sum(r['status'] == 'fail' for r in results),
          'skipped': sum(r['status'] == 'skip' for r in results), 'results': results}
args.report.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ('passed', 'failed', 'skipped')}))
raise SystemExit(1 if report['failed'] else 0)
