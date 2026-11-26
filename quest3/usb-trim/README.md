# Experimental USB-only target reduction, pass 1

## Pass 3 completed

trim3.fragment removes embedded BTF, all-section data symbol names and KUnit.
Function kallsyms, host DWARF/frame pointers, pstore, checked hardening and
USB/QMP providers are retained. The target is an effective Image at most
32 MiB for the separately reviewed default-CMA route. The separate Image build
passed checks: image_size is 31.25 MiB, down 4.6875 MiB from trim2.
The 0.75 MiB size margin is not spare CMA capacity: the rounded Image request
still uses all nominal 32 MiB. Separate Image/initrd/DT requests total 36 MiB;
the combined window still does not fit. No pool availability, ownership or
boot readiness is inferred; no allocator was called or device boot attempted.
Use `--profile usb-trim3` with a new output/release. See
[preparation and tradeoffs](../../docs/reports/2026-11-17-usb-trim3-preparation.md).
See the [measured result](../../docs/reports/2026-11-17-usb-trim3-result.md) and
trim3-verification.json, trim3-geometry.json, trim3-allocation-assessment.json
and trim3-comparison.json. Artifacts and host DWARF were archived privately.

## Pass 2 completed

trim2.fragment removes extra networking and disk/network filesystem consumers
from the measured trim1 baseline, without removing storage/DMA controllers.
Prepared config/diff/metadata and result files are included. The separate trim2
Image build passed artifact checks; image_size is 35.9375 MiB, still above the
historically observed 24 MiB run. No device boot was attempted. Use `prepare-usb-trim.py
--profile usb-trim2` and a distinct output/release; see the project trim2 report.

## Completed pass 1

Status: trim1 Image build completed and artifact checks passed. image_size is
39.125 MiB, down from 43.125 MiB but still larger than the historical 24 MiB
MOVABLE run. No device boot or page ownership was established. See
trim1-verification.json, trim1-geometry.json and trim1-comparison.json.

Baseline: completed QMP candidate, `quest3/configs/ram-first-qmp.config`.
Trial config: `quest3/configs/usb-trim1.config`.
Plan: trim1.fragment; generated checks/diff: trim1-preparation.json and
trim1-config.diff. None changes the stock kernel or the existing candidate.

## Deliberately removed

Video/media/display core, HID/USB HID/joysticks, wireless/Bluetooth, IPv6,
netfilter and USB mass storage. This is for direct isolated USB ECM + static
IPv4 BusyBox, not a general Android, desktop or routed-network kernel.
It has no netfilter firewall; retain the isolated development-link restriction.

The GKI convenience root and selected display/media/wireless selectors had to
be removed because they re-enabled unwanted subsystems. GKI module compatibility
is not a goal for this standalone target; do not mix vendor stock modules with it.

Audio is RETAINED in pass 1. An earlier draft removed it but demoted the shared
DMA_VIRTUAL_CHANNELS framework to a module. That draft was rejected rather than
enabling an unrelated DMA hardware driver to force the framework built-in.

## Guards

The preparation script verifies the existing explicit USB/provider fragment,
QMP/AOSS, IPv4, configfs/ECM, RAM filesystems, pstore and shared DMA remain
built-in. CFI/SCS/Full LTO/MODVERSIONS are required. It also checks baseline
SELinux, seccomp and selected hardening settings remain unchanged.
These checks are not proof of full hardware dependency closure.

## Reproduction

Prepare sources/toolchain/pahole and the reviewed host OpenSSL patch as in
docs/BUILD.md. Use a NEW output directory:

```sh
python3 tools/prepare-usb-trim.py --out .work/usb-trim1-new-out
Q3_OUT="$PWD/.work/usb-trim1-new-out" \
Q3_LOCALVERSION=-gd7102a837402-q3-usb-trim1 \
  tools/q3make -j2 HOSTCFLAGS=-DOPENSSL_NO_ENGINE Image
```

This build requests Image only, not the full module set. After successful
completion, check the new artifact with:

```sh
python3 tools/verify-qmp-candidate.py --out .work/usb-trim1-new-out \
  --profile usb-trim1 --image-only
```

Image-only verification uses vmlinux.symvers and does not claim complete module
build/ABI validation. Measure image_size, not just file size, and recompute
geometry. Even if it fits a previously sampled MOVABLE run, that sample is
historical; full PFN validity, ownership and DMA/shutdown remain unproven.
