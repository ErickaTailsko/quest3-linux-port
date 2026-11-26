#!/usr/bin/env bash
# Separate host build only. Never installs, loads modules, or contacts a Quest.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=${Q3_WORK_ROOT:-"$repo/.work"}
kernel=${Q3_KERNEL:-"$work/kernel"}
export Q3_OUT=${Q3_OUT:-"$work/qmp-candidate-out"}
export Q3_LOCALVERSION=-gd7102a837402-q3-ram-first-qmp
jobs=${Q3_JOBS:-2}
configure_only=false
if [[ ${1:-} == --configure-only && $# == 1 ]]; then
    configure_only=true
elif [[ $# != 0 ]]; then
    echo 'Usage: build-qmp-candidate.sh [--configure-only]' >&2; exit 2
fi
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'Q3_JOBS must be positive' >&2; exit 2; }
[[ $(git -C "$kernel" rev-parse HEAD) == dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f ]] || {
    echo 'Unexpected source revision' >&2; exit 1;
}
host_args=()
dirty=$(git -C "$kernel" status --porcelain --untracked-files=all)
if [[ ${Q3_HOST_NO_ENGINE:-0} == 1 ]]; then
    # Explicit host-only exception: refuse any source change beyond the reviewed patch.
    [[ "$dirty" == ' M scripts/extract-cert.c' &&
       $(sha256sum "$kernel/scripts/extract-cert.c" | cut -d' ' -f1) == 28b8eb37b33dd372d2d189687b2edc6bec8660d784fc3fb9fc4425f295a4ea0b ]] || {
        echo 'Expected exact reviewed extract-cert patch only' >&2; exit 1;
    }
    host_args+=(HOSTCFLAGS=-DOPENSSL_NO_ENGINE)
elif [[ -n "$dirty" ]]; then
    echo 'Source tree is modified; preserve and review it first' >&2; exit 1
fi
# Check tool prerequisites before creating an output directory.
llvm=${Q3_LLVM:-"$work/clang-prebuilts/clang-r450784e/bin"}
pahole=${Q3_PAHOLE:-"$work/pahole-build/pahole"}
for tool in "$llvm/clang" "$llvm/ld.lld" "$pahole"; do
    test -x "$tool" || { echo "Missing tool: $tool" >&2; exit 1; }
done
[[ ! -e "$Q3_OUT" ]] || { echo "Preserving existing output: $Q3_OUT" >&2; exit 1; }
mkdir -p "$Q3_OUT"
cp "$repo/quest3/configs/ram-first.config" "$Q3_OUT/.config"
cp "$repo/quest3/qmp-audit/builtin-proposal.config" "$Q3_OUT/proposed-fragment.config"
"$repo/tools/q3make" "${host_args[@]}" olddefconfig 2>&1 | tee "$Q3_OUT/configure.log"
cp "$Q3_OUT/.config" "$Q3_OUT/before-qmp.config"
"$kernel/scripts/config" --file "$Q3_OUT/.config" --enable QCOM_AOSS_QMP --enable MSM_QMP
"$repo/tools/q3make" "${host_args[@]}" olddefconfig 2>&1 | tee -a "$Q3_OUT/configure.log"
python3 - "$Q3_OUT/.config" <<'PY'
import sys
from pathlib import Path
lines = set(Path(sys.argv[1]).read_text().splitlines())
for key in ('QCOM_AOSS_QMP', 'MSM_QMP', 'CFI_CLANG', 'CFI_CLANG_SHADOW',
            'SHADOW_CALL_STACK', 'LTO_CLANG_FULL', 'MODVERSIONS',
            'MAILBOX', 'COMMON_CLK', 'PM', 'QCOM_IPCC', 'ARM_GIC_V3'):
    if 'CONFIG_' + key + '=y' not in lines:
        raise SystemExit('Required configuration lost: ' + key)
print('PASS QMP built-ins, dependencies and required protections')
PY
"$kernel/scripts/diffconfig" "$Q3_OUT/before-qmp.config" "$Q3_OUT/.config" > "$Q3_OUT/qmp-config.diff"
"$llvm/clang" --version > "$Q3_OUT/compiler-version.txt"
git -C "$kernel" rev-parse HEAD > "$Q3_OUT/source-revision.txt"
if "$configure_only"; then
    echo "Configuration prepared only: $Q3_OUT; no Image built"
    exit 0
fi
"$repo/tools/q3make" -j"$jobs" "${host_args[@]}" Image modules 2>&1 | tee "$Q3_OUT/build.log"
python3 "$repo/tools/verify-qmp-candidate.py" --out "$Q3_OUT" > "$Q3_OUT/candidate-verification.json"
sha256sum "$Q3_OUT/arch/arm64/boot/Image" "$Q3_OUT/.config" > "$Q3_OUT/candidate-SHA256SUMS"
echo "Experimental candidate built in $Q3_OUT; no device operations; handoff unvalidated"
