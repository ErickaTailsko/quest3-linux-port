#!/usr/bin/env python3
"""Exercise the production C helper, including 64-bit boundary inputs."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = r'''
#include <stdint.h>
#include <errno.h>
#include <assert.h>
typedef uint64_t u64;
#include "quest3-layout.h"
int main(void) {
 u64 entry = 123;
 assert(!qkx_image_layout(0, 0x2b20000, 43565568, 10, &entry));
 assert(entry == 0x90000000);
 assert(!qkx_image_layout(0x80000, 0x2b20000, 43565568, 10, &entry));
 assert(entry == 0x90080000);
 assert(!qkx_image_layout(0, 0x3000000, 64, 10, &entry));
 assert(!qkx_image_layout(0, 0x2ffffff, 64, 10, &entry));
 assert(!qkx_image_layout(0x80000, 0x2f80000, 64, 10, &entry));
 assert(qkx_image_layout(0, 0x3000001, 64, 10, &entry) == -EINVAL);
 assert(qkx_image_layout(0x80000, 0x2f80001, 64, 10, &entry) == -EINVAL);
 assert(qkx_image_layout(1, 64, 64, 10, &entry) == -EINVAL);
 assert(qkx_image_layout(UINT64_MAX, 64, 64, 10, &entry) == -EINVAL);
 assert(qkx_image_layout(0, UINT64_MAX, 64, 10, &entry) == -EINVAL);
 assert(qkx_image_layout(0, 64, 65, 10, &entry) == -EINVAL);
 assert(qkx_image_layout(0, 63, 63, 10, &entry) == -EINVAL);
 assert(qkx_image_layout(0, 64, 64, 11, &entry) == -EINVAL);
 assert(qkx_image_layout(0, 64, 64, 2, &entry) == -EINVAL);
 assert(qkx_image_layout(0, 64, 64, 12, &entry) == -EINVAL);
 assert(qkx_image_layout(0, 64, 64, 14, &entry) == -EINVAL);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / 'test.c'; binary = Path(tmp) / 'test'
    src.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                    '-I', str(root / 'module'), str(src), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS production C layout: offset 0/512KiB, exact limits, rounding, overflow, flags and truncated image')
