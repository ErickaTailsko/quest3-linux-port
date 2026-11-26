#!/usr/bin/env python3
"""Run local checks only; no adb, module loading or device operations."""
from pathlib import Path
import hashlib, json, re, subprocess, sys, time
r=Path(__file__).resolve().parent
checks=['tests/x18-frame-test.py','tests/scm-host-test.py','tests/scm-control-order-test.py',
        'tests/platform-host-test.py','tests/cpu-flow-test.py','tests/preflight-dispatch-test.py',
        'tests/collect-readonly-test.py','verify-cfi-guards.py','verify-platform.py','verify.py']
log=(r/'checklist-build.log').read_text()
assert not re.search(r'error:|warning:|FAILED|\*\*\*',log), 'Build log contains errors or warnings'
results=[]
with (r/'local-checks.log').open('w') as output:
    for check in checks:
        start=time.monotonic()
        result=subprocess.run([sys.executable,str(r/check)],cwd=r,capture_output=True,text=True)
        output.write(f'[{check}] exit={result.returncode}\n'+result.stdout+result.stderr+'\n');output.flush()
        results.append({'check':check,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3)})
        print(f'{"PASS" if result.returncode==0 else "FAIL"}: {check}',flush=True)
        if result.returncode:break
sources={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'module').iterdir() if p.suffix in ('.c','.h','.S') and not p.name.endswith('.mod.c')}
report={'passed':len(results)==len(checks) and all(x['exit_code']==0 for x in results),'checks':results,
        'hardware_tested':False,'source_sha256':sources,'build_log_sha256':hashlib.sha256((r/'checklist-build.log').read_bytes()).hexdigest()}
(r/'local-checks.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
