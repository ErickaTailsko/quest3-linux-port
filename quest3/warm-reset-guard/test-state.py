#!/usr/bin/env python3
"""Exercise the actual atomic ownership helper; no firmware or device is used."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent
source = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdio.h>
enum reboot_mode {REBOOT_UNDEFINED=-1, REBOOT_COLD=0, REBOOT_WARM, REBOOT_HARD, REBOOT_SOFT, REBOOT_GPIO};
static enum reboot_mode reboot_mode;
static int exchanges;
static enum reboot_mode exchange(enum reboot_mode *p,enum reboot_mode expected,enum reboot_mode desired) {
 enum reboot_mode old=*p;exchanges++;if(old==expected)*p=desired;return old;
}
#define cmpxchg exchange
#include "q3_warm_state.h"
int main(void) {
 struct q3_warm_state a={0}, b={0};int i;
 assert(!q3_warm_release(&a)&&!exchanges);
 for(i=-1;i<=7;i++) {
  reboot_mode=i;
  if(i==REBOOT_COLD)continue;
  assert(q3_warm_acquire(&a)==-EBUSY&&!a.owned&&reboot_mode==i);
 }
 reboot_mode=REBOOT_COLD;
 assert(!q3_warm_acquire(&a)&&a.owned&&reboot_mode==REBOOT_WARM);
 assert(q3_warm_acquire(&a)==-EBUSY&&a.owned&&reboot_mode==REBOOT_WARM);
 assert(q3_warm_acquire(&b)==-EBUSY&&!b.owned);
 assert(q3_warm_release(&a)&&reboot_mode==REBOOT_COLD&&!a.owned);
 assert(!q3_warm_release(&a)&&reboot_mode==REBOOT_COLD);
 assert(!q3_warm_acquire(&a));
 reboot_mode=REBOOT_HARD;
 assert(!q3_warm_release(&a)&&reboot_mode==REBOOT_HARD&&!a.owned);
 reboot_mode=REBOOT_COLD;
 assert(!q3_warm_acquire(&a));
 reboot_mode=REBOOT_COLD;
 assert(!q3_warm_release(&a)&&reboot_mode==REBOOT_COLD);
 puts("PASS production helper: only COLD acquired, atomic compare/update, duplicate owner refused, rollback and foreign policy preserved");
}
'''
with tempfile.TemporaryDirectory() as temp:
    c = Path(temp) / 'test.c'; binary = Path(temp) / 'test'
    c.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                    '-I', str(root), str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
