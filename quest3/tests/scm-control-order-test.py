#!/usr/bin/env python3
from pathlib import Path
import subprocess, tempfile
r=Path(__file__).resolve().parents[1];s=(r/'module/loader.c').read_text()
a=s.index('static bool qkx_control_modes_conflict');b=s.index('static int __init qkx_init',a);helper=s[a:b]
a=s.index('\t\tif (!ret && core_hang_control == 1)',b);b=s.index('#ifdef QKX_ENABLE_EXPERIMENTAL_JUMP',a);phase=s[a:b]
init=s[s.index('static int __init qkx_init'):]
assert init.index('qkx_identity_map()')<init.index('qkx_core_hang_configure(2)')
assert init.index('qkx_control_modes_conflict()')<init.index('qkx_resolve()')
prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
static unsigned int core_hang_control,secure_watchdog_control,test_cpus;
static bool execute,test_transition,test_full_copy,warm_reset_test;
static int calls,fail_call;
static char order[8];
static int qkx_core_hang_configure(unsigned int mode) { order[calls++]=mode==1?'c':'C';return calls==fail_call?-EIO:0; }
static int qkx_secure_watchdog_configure(unsigned int mode) { order[calls++]=mode==1?'s':'S';return calls==fail_call?-EIO:0; }
'''
tests=r'''
int main(void) {
 bool *flags[]={&execute,&test_transition,&test_full_copy,&warm_reset_test};
 core_hang_control=2;secure_watchdog_control=2;assert(qkx_control_modes_conflict());
 for(int target=0;target<2;target++) {
  core_hang_control=target?0:2;secure_watchdog_control=target?2:0;
  assert(!qkx_control_modes_conflict());
  for(unsigned int i=0;i<sizeof(flags)/sizeof(flags[0]);i++) {
   *flags[i]=true;assert(qkx_control_modes_conflict());*flags[i]=false;
  }
  test_cpus=1;assert(qkx_control_modes_conflict());test_cpus=0;
  calls=0;assert(run(-ENOENT)==-ENOENT && !calls); /* staging failed */
 }
 core_hang_control=2;secure_watchdog_control=1;calls=0;fail_call=1;
 assert(run(0)==-EIO && calls==1 && order[0]=='s');
 calls=0;fail_call=0;assert(!run(0) && calls==2 && order[0]=='s' && order[1]=='C');
 core_hang_control=1;secure_watchdog_control=2;calls=0;fail_call=1;
 assert(run(0)==-EIO && calls==1 && order[0]=='c');
 calls=0;fail_call=2;assert(run(0)==-EIO && calls==2 && order[1]=='S');
 core_hang_control=1;secure_watchdog_control=1;execute=true;assert(!qkx_control_modes_conflict());
 puts("PASS: staging failure causes no SCM access; read checks precede writes; mutation errors propagate; two mutations and destructive/test combinations rejected");
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'test.c').write_text(prefix+helper+'static int run(int ret) {\n'+phase+'return ret;\n}\n'+tests)
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
