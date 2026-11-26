#!/usr/bin/env bash
# Requires GNU make, native C compiler, and a static-capable ARM64 cross GCC.
# Usage: CROSS_COMPILE=aarch64-linux-gnu- ./rebuild-busybox.sh NEW_WORK_DIRECTORY
set -euo pipefail
base=$(cd -- "$(dirname -- "$0")" && pwd)
work=$(realpath -m -- "${1:?Specify a new work directory}")
[[ ! -e "$work" ]] || { echo "Work directory already exists: $work" >&2; exit 1; }
mkdir -p -- "$work"
cd -- "$base"
echo 'b8cc24c9574d809e7279c3be349795c5d5ceb6fdf19ca709f80cde50e47de314  busybox-1.36.1.tar.bz2' | sha256sum -c -
tar -xjf busybox-1.36.1.tar.bz2 -C "$work"
cp busybox.config "$work/busybox-1.36.1/.config"
cd "$work/busybox-1.36.1"
python3 - <<'PY'
from pathlib import Path
import os,re
p=Path('.config');s=p.read_text()
s=re.sub(r'^CONFIG_SYSROOT=.*$', 'CONFIG_SYSROOT="'+os.environ.get('BUSYBOX_SYSROOT','')+'"',s,flags=re.M)
p.write_text(s)
PY
export CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"
export ARCH=arm64
python3 - <<'PY'
import subprocess
with open('../configure.log','wb') as log:
    subprocess.run(['make','oldconfig'],input=b'\n'*4096,stdout=log,stderr=subprocess.STDOUT,check=True)
PY
make -j"${JOBS:-4}" > ../build.log 2>&1
cp busybox ../busybox-arm64
printf 'BusyBox: %s/busybox-arm64\n' "$work"
