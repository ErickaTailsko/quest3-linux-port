#!/usr/bin/env python3
"""Compile the actual early-init preflight branch and test conflicting modes."""
from pathlib import Path
import subprocess, tempfile
r=Path(__file__).resolve().parents[1]
s=(r/'module/loader.c').read_text()
a=s.index('\tif (preflight_only == 1)',s.index('static int __init qkx_init'))
b=s.index('\tif (test_cpus >',a)
branch=s[a:b]
flags=['execute','test_cpus','test_transition','test_full_copy','warm_reset_test','core_hang_control','secure_watchdog_control','preserve_watchdog','watchdog_recovery','watchdog_control','post_shutdown_probe','flush_rpmh','suspend_syncboss','disconnect_qmp','phase_delay_ms']
prefix='''#include <stdbool.h>
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#define pr_err(...) do {} while(0)
static int board=1, calls, board_calls, result;
static int of_machine_is_compatible(const char *s) { (void)s; board_calls++; return board; }
static int qkx_platform_preflight(void) { calls++; return result; }
'''
prefix+='static unsigned int preflight_only, '+','.join(flags)+';\n'
helper=s[s.index('static bool qkx_control_modes_conflict'):s.index('static int __init qkx_init')]
code=prefix+helper+'static int dispatch(void) {\n'+branch+'return 777;\n}\n'
code+='int main(void) { unsigned int *flags[]={'+','.join('&'+f for f in flags)+'};\n'
code+='''preflight_only=1; assert(dispatch()==0 && calls==1);
result=-ENODEV; assert(dispatch()==-ENODEV && calls==2);
board=0; assert(dispatch()==-ENODEV && calls==2); board=1;
for (unsigned int i=0;i<sizeof(flags)/sizeof(flags[0]);i++) {
 int previous=board_calls; *flags[i]=1;
 assert(dispatch()==-EINVAL && calls==2 && board_calls==previous); *flags[i]=0;
}
preflight_only=0; assert(dispatch()==777);
preflight_only=2; assert(dispatch()==777);
preflight_only=3; assert(dispatch()==777);
puts("PASS: actual init branch rejects all 15 mixed modes before device access, propagates errors, isolates preflight=1");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);(p/'test.c').write_text(code)
    subprocess.run(['cc','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
