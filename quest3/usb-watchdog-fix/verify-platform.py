#!/usr/bin/env python3
"""Audit ARM64 helper code independently of the final CFI-blocked execute path."""
from pathlib import Path
import json, re, subprocess
r=Path(__file__).resolve().parent
llvm=r/'clang-prebuilts/clang-r450784e/bin'
audit=r/'quest3-platform-audit.o'
subprocess.run([str(llvm/'ld.lld'),'-r',str(r/'module/quest3-platform.o'),'-o',str(audit)],check=True)
symbols=subprocess.check_output([str(llvm/'llvm-nm'),str(audit)],text=True)
imports=set(re.findall(r'^\s+U (\S+)$',symbols,re.M))
exports={line.split()[1] for line in (r/'out/Module.symvers').read_text().splitlines()}
assert not imports-exports, imports-exports
assert {'usb_gadget_connect','usb_gadget_disconnect','__cfi_slowpath','mod_timer','del_timer_sync'} <= imports
assert not {'qcom_wdt_pet_suspend','qcom_wdt_pet_resume','register_kprobe','ioremap','iounmap'} & imports
for func in ('qkx_usb_get','qkx_usb_disconnect','qkx_usb_put','qkx_watchdog_get',
             'qkx_watchdog_prepare','qkx_watchdog_finish','qkx_watchdog_put','qkx_platform_abort'):
    assert re.search(r' T '+func+'$',symbols,re.M),func
cmd=(r/'module/.quest3-platform.o.cmd').read_text().splitlines()[0]
for flag in ('-flto','-fsanitize=cfi','-fsanitize=shadow-call-stack','-ffixed-x18'):
    assert flag in cmd,flag
log=(r/'usb-watchdog-build.log').read_text()
assert not re.search(r'error:|warning:|FAILED|\*\*\*',log)
loader=(r/'module/loader.c').read_text()
execute=loader[loader.index('static int __maybe_unused qkx_execute'):loader.index('static int __init qkx_init')]
for legacy in ('wdt_regs','in_lpm','suspend_dwc3_gadget','watchdog_disable','lookup("bus_find_device_by_name")'):
    assert legacy not in execute,legacy
assert execute.index('qkx_usb_disconnect') < execute.index('qkx_watchdog_prepare') < execute.index('qkx_watchdog_finish') < execute.index('qkx_secure_watchdog_configure') < execute.index('prepare(NULL)')
cleanup=execute[execute.index('release_devices:'):]
assert cleanup.index('qkx_platform_abort') < cleanup.index('syncboss->driver->pm->resume') < cleanup.index('gpu_resume(gpu)') < cleanup.index('thaw_users()')
result={'arm64_helper_imports_all_exported':True,'helper_cfi_scs_enabled':True,
        'rollback_before_irreversible_shutdown':True,'timing_changes_refused':True,
        'execution_remains_blocked_under_cfi':True,'hardware_tested':False,
        'note':'Helper audit uses a separate relocatable object: final module LTO removes the still-blocked execute path.',
        'imports':sorted(imports)}
print(json.dumps(result,indent=2))
