#!/usr/bin/env bash
set -euo pipefail
Q3_ROOT=/workspace/quest3-build
mkdir -p "$Q3_ROOT/sysroot"
for q3deb in "$Q3_ROOT"/apt/archives/*.deb; do
    dpkg-deb -x "$q3deb" "$Q3_ROOT/sysroot"
done
source "$Q3_ROOT/env.sh"
cmake --fresh -S "$Q3_ROOT/inputs/dwarves-quest3-cfi" -B "$Q3_ROOT/pahole-build" \
    -DCMAKE_BUILD_TYPE=Release -DLIBBPF_EMBEDDED=ON \
    -DZLIB_LIBRARY=/lib/x86_64-linux-gnu/libz.so.1 \
    -DCMAKE_PREFIX_PATH="$Q3_SYSROOT/usr" \
    -DCMAKE_BUILD_RPATH="$Q3_SYSROOT/usr/lib/x86_64-linux-gnu"
cmake --build "$Q3_ROOT/pahole-build" --target pahole -j4
"$Q3_ROOT/pahole-build/pahole" --version
