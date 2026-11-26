#!/usr/bin/env bash
set -euo pipefail
source /workspace/quest3-build/env.sh
cd "$Q3_ROOT"
test -x "$Q3_ROOT/pahole-build/pahole"
"$Q3_ROOT/pahole-build/pahole" --version
"$Q3_ROOT/q3make" olddefconfig 2>&1 | tee configure.log
for q3option in SHADOW_CALL_STACK LTO_CLANG_FULL CFI_CLANG CFI_CLANG_SHADOW MODVERSIONS META_SAMPLE_PGO; do
    if ! grep -qx "CONFIG_${q3option}=y" out/.config; then
        printf 'Required option not enabled: CONFIG_%s\n' "$q3option" >&2
        exit 1
    fi
done
"$Q3_ROOT/q3make" -j4 Image modules 2>&1 | tee kernel-build.log
test -s out/vmlinux
test -s out/arch/arm64/boot/Image
test -s out/Module.symvers
test "$(cat out/include/config/kernel.release)" = 5.10.246-gd7102a837402
"$Q3_ROOT/q3make" -j4 M="$Q3_ROOT/module" \
    KCFLAGS="-I$Q3_ROOT/local-include" modules 2>&1 | tee module-build.log
printf '\nKernel and external module build commands completed successfully.\n'
