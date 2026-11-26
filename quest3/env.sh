#!/usr/bin/env bash
Q3_ROOT=/workspace/quest3-build
Q3_SYSROOT="$Q3_ROOT/sysroot"
Q3_LLVM="$Q3_ROOT/clang-prebuilts/clang-r450784e/bin"
export Q3_ROOT Q3_SYSROOT Q3_LLVM
export PATH="$Q3_LLVM:$Q3_SYSROOT/usr/bin:$PATH"
export LD_LIBRARY_PATH="$Q3_SYSROOT/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export CPATH="$Q3_SYSROOT/usr/include${CPATH:+:$CPATH}"
export LIBRARY_PATH="$Q3_SYSROOT/usr/lib/x86_64-linux-gnu${LIBRARY_PATH:+:$LIBRARY_PATH}"
export PKG_CONFIG_PATH="$Q3_SYSROOT/usr/lib/x86_64-linux-gnu/pkgconfig:$Q3_SYSROOT/usr/share/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export BISON_PKGDATADIR="$Q3_SYSROOT/usr/share/bison"
export M4="$Q3_SYSROOT/usr/bin/m4"
