#!/usr/bin/env python3
"""Compile the pinned production qmp_open body against host-only MMIO/wait mocks."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=repo / '.work/kernel/drivers/soc/qcom/qcom_aoss.c')
args = parser.parse_args()
data = args.source.read_bytes()
expected = '90655ebf973345f490f5c6a223400b4dd213560069b9446b421b23526841d956'
if hashlib.sha256(data).hexdigest() != expected:
    raise SystemExit('Source hash differs from audited revision; review before testing')
source = data.decode()
constants = '\n'.join(re.findall(r'^#define QMP_(?:DESC_\w+|STATE_\w+|MAGIC|VERSION)\s+.+$', source, re.M))
production = source[source.index('static bool qmp_magic_valid('):source.index('static void qmp_close(')]
harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
#define GENMASK(h,l) ((uint32_t)((UINT64_C(0xffffffff) >> (31-(h))) & (UINT64_C(0xffffffff) << (l))))
#define HZ 100
#define dev_err(...) ((void)0)
struct qmp { unsigned char *msgram; void *dev; size_t offset, size; int event; };
static int writes, kicks, waits, fail_step;
static u32 readl(void *p) { u32 value; memcpy(&value,p,4); return value; }
static void writel(u32 value, void *p) { memcpy(p,&value,4); writes++; }
static void qmp_kick(struct qmp *q) { (void)q; kicks++; }
'''
simulation = r'''
static void remote_wait(struct qmp *q) {
    unsigned offsets[] = {QMP_DESC_MCORE_LINK_STATE_ACK,
                          QMP_DESC_UCORE_CH_STATE, QMP_DESC_MCORE_CH_STATE_ACK};
    assert(waits < 3);
    u32 state = (++waits == fail_step) ? QMP_STATE_DOWN : QMP_STATE_UP;
    memcpy(q->msgram + offsets[waits-1], &state, 4);
}
#define wait_event_timeout(event, condition, timeout) (remote_wait(qmp), (condition) ? 1 : 0)
'''
tests = r'''
int main(void) {
    u32 registers[64];
    struct qmp q = {.msgram=(unsigned char *)registers};
    for (int mode=0; mode<8; mode++) {
        memset(registers,0,sizeof(registers));
        registers[QMP_DESC_MAGIC/4]=QMP_MAGIC;
        registers[QMP_DESC_VERSION/4]=QMP_VERSION;
        registers[QMP_DESC_MCORE_MBOX_SIZE/4]=128;
        registers[QMP_DESC_MCORE_MBOX_OFFSET/4]=64;
        registers[QMP_DESC_UCORE_LINK_STATE/4]=QMP_STATE_UP;
        if (mode==1) {
            registers[QMP_DESC_MCORE_LINK_STATE/4]=QMP_STATE_UP;
            registers[QMP_DESC_MCORE_LINK_STATE_ACK/4]=QMP_STATE_UP;
            registers[QMP_DESC_MCORE_CH_STATE/4]=QMP_STATE_UP;
            registers[QMP_DESC_MCORE_CH_STATE_ACK/4]=QMP_STATE_UP;
            registers[QMP_DESC_UCORE_CH_STATE/4]=QMP_STATE_UP;
        }
        if (mode==2) registers[QMP_DESC_MAGIC/4]=0;
        if (mode==3) registers[QMP_DESC_VERSION/4]=99;
        if (mode==4) registers[QMP_DESC_MCORE_MBOX_SIZE/4]=0;
        writes=kicks=waits=0; fail_step=mode>=5 ? mode-4 : 0;
        int result=qmp_open(&q);
        if (mode>=2 && mode<=4) {
            assert(result==-EINVAL && !writes && !kicks && !waits);
        } else if (mode>=5) {
            assert(result==-ETIMEDOUT && waits==fail_step);
            assert(registers[QMP_DESC_MCORE_LINK_STATE/4]==QMP_STATE_DOWN);
            if (fail_step>=2) assert(registers[QMP_DESC_MCORE_CH_STATE/4]==QMP_STATE_DOWN);
        } else {
            assert(!result && writes==4 && kicks==3 && waits==3);
            assert(q.size==128 && q.offset==64);
            assert(registers[QMP_DESC_UCORE_CH_STATE_ACK/4]==QMP_STATE_UP);
        }
    }
    puts("PASS production qmp_open: fresh/inherited-UP state, invalid metadata, three timeout paths; host mocks only, no firmware/IRQ/timing validation");
}
'''
with tempfile.TemporaryDirectory(prefix='qmp-handshake-') as temporary:
    folder = Path(temporary)
    (folder / 'test.c').write_text(harness + constants + '\n' + simulation + production + tests)
    subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    str(folder / 'test.c'), '-o', str(folder / 'test')], check=True, timeout=60)
    subprocess.run([str(folder / 'test')], check=True, timeout=10)
