#!/usr/bin/env bash
set -euo pipefail
source /workspace/quest3-build/env.sh
cd "$Q3_ROOT"
python3 verify.py | tee verification.log
mkdir -p artifacts/modules artifacts/reference-kernel artifacts/logs artifacts/build-tools artifacts/module-source/soc/qcom
cp out/arch/arm64/boot/Image artifacts/reference-kernel/Image
cp out/.config artifacts/reference-kernel/kernel.config
cp out/Module.symvers out/System.map artifacts/reference-kernel/
cp module/quest_kexec.ko module/marker_read.ko module/usb_log.ko artifacts/modules/
cp module/loader.c module/transition.S module/marker_read.c module/usb_log.c module/Makefile artifacts/module-source/
cp local-include/soc/qcom/scm.h artifacts/module-source/soc/qcom/
cp validation.json build-info.json runtime-review.md input-source-sha256.txt artifacts/
cp README.md artifacts/BUILD.md
cp device.config artifacts/reference-kernel/device.config
cp configure.log kernel-build.log module-build.log pahole-configure.log pahole-build.log verification.log artifacts/logs/
cp env.sh q3make build.sh setup-local-tools.sh verify.py package.sh artifacts/build-tools/
cp apt/package-sha256.txt artifacts/build-tools/debian-package-sha256.txt
tar -czf artifacts/patched-pahole-source.tar.gz -C inputs dwarves-quest3-cfi
(cd artifacts && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
tar -czf quest3-cloud-build.tar.gz -C artifacts .
sha256sum quest3-cloud-build.tar.gz > quest3-cloud-build.tar.gz.sha256
ls -lh quest3-cloud-build.tar.gz quest3-cloud-build.tar.gz.sha256
