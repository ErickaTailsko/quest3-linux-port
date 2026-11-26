# Quest 3 cloud build workspace

This directory prepares future builds without changing the published environment draft.
Use the existing isolated checkouts; no Git worktree is needed.

## Sources and tools

- Kernel: facebookincubator/oculus-linux-kernel, commit dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f.
- AOSP clang prebuilts: android14-release, commit 425c8149f17c8d9914bf690b4d5abe45a13fb993, sparse checkout clang-r450784e.
- Clang and LLD: 14.0.7, matching the device compiler version.
- Native prerequisites: signature-verified Debian trixie packages downloaded into apt/archives and extracted into sysroot, without system installation. This is a native host tools prefix, not a target root filesystem.
- Native package checksums are recorded in apt/package-sha256.txt.

## Commands

Run `/workspace/quest3-build/q3make <targets>` from any directory.
The wrapper activates env.sh, sets the ARM64 target explicitly, and uses kernel/ and out/.
Do not drop CROSS_COMPILE: this older kernel uses it to select the Clang target even with LLVM=1.
The output release is explicitly set to 5.10.246-gd7102a837402. That string alone does not prove identity with the device's private source revision.

out/.config was derived from the uploaded device configuration. Preserve and check CONFIG_SHADOW_CALL_STACK=y, CONFIG_LTO_CLANG_FULL=y, CONFIG_CFI_CLANG=y, CONFIG_CFI_CLANG_SHADOW=y, CONFIG_MODVERSIONS=y and CONFIG_META_SAMPLE_PGO=y after configuration updates. LOCALVERSION_AUTO is disabled to avoid appending the public checkout hash.

## Validation

The complete kernel build and external module build finished with BUILD_EXIT_CODE=0. Validation is recorded in validation.json and verification.log:

- All required options are enabled: SCS, Full LTO, CFI, CFI shadow, MODVERSIONS and sample PGO.
- All 15,919 exported kernel CRCs match the supplied final local build.
- External module CRCs match: quest_kexec 46, marker_read 13, usb_log 23; no mismatches.
- Each external module contains __cfi_check and was compiled with the SCS and CFI flags.
- BTFIDS completed. vfs_truncate is BTF function 105614 and is present in the sorted d_path allowlist. The entire allowlist matches the expected function names. Individual symbol offsets cannot identify entries after resolve_btfids sorts the set.
- Independent bpftool decoding of the generated BTF succeeded; the raw dump is in out/vmlinux-btf.raw.
- Two nonfatal frame-size warnings were reported for existing video/camera driver functions; full messages are in validation.json and kernel-build.log.

olddefconfig, prepare/scripts and a representative init/main.o build were also verified before the full build. No on-device load or execution test has been performed. Review runtime-review.md before any such test. Build success does not establish device compatibility.

## Supplied inputs and reproducible build

The locally patched dwarves/Pahole source is now retained in inputs/dwarves-quest3-cfi. Its btf_encoder.c excludes .cfi_jt suffixes from function ambiguity analysis. Pahole 1.32 is built in pahole-build with the embedded libbpf supplied in the archive. The wrapper selects that exact binary. setup-local-tools.sh reproduces native tool extraction and the patched Pahole build using the retained signature-verified Debian packages. The stock Pahole 1.30 in sysroot is not used for kernel builds.

The final SCS-enabled input archive is retained in inputs/. Module source files were copied into module/ without old generated object files, and the supplied legacy SCM header is isolated in local-include/soc/qcom/scm.h. Only the external module build receives that include path. Treat the legacy SCM header as unvalidated; official headers use a different interface.

build.sh runs configuration, checks required options, builds Image and all configured modules, then builds the three external modules. It preserves the underlying make exit status across log capture. Run python3 verify.py after a successful build for ELF/CRC/CFI/SCS/BTF checks. See validation.json for the outcome. The full build is not validated until that file exists and represents the current sources and outputs.

No module has been loaded and no device operation has been performed. SCM calls, indirect calls under CFI, watchdog handling and USB power-state handling still need review before runtime testing.
Do not flash the locally rebuilt Image merely to test the module.
