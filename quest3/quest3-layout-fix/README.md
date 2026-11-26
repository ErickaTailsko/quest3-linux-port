# Quest 3: Image layout correction (offline)

No boot or physical transition has been tested. The CFI execution guard remains active.
The module uses the stock running-kernel ABI 5.10.246-gd7102a837402, CFI, SCS and Full LTO.

The candidate Image has text_offset=0. Entry is now 0x90000000; legacy offset
0x80000 remains supported with entry 0x90080000. Image occupies at most the
space before initrd 0x93000000; DTB is placed at 0x93200000.

check-layout.py checks the full 52 MiB window against visible iomem resources
(including nested reservations), DT reserve entries and reserved-memory reg.
Dynamic DT allocations require a matching root-readable iomem capture. This
check does not reserve destination pages against Android allocation or DMA.
The module's RAM walker only checks the containing System RAM extent.

Run against YOUR fresh USB-modified DTB, Image and initramfs. --out-dtb creates
a new file and changes only linux,initrd-start/end in /chosen. All other
properties, including USB settings, bootargs and watchdog policy, are preserved.
A matching chosen address alone does not make the target boot-ready. Bootargs,
DMA quiescence, CFI-safe handoff and retained logging still need resolution.

Example (fish):

    python3 check-layout.py --image ~/quest3-ram-first-candidate/Image --initramfs ~/quest3-usb2-minimal/quest3-usb2-minimal.cpio.gz --dtb ~/quest3-usb2-peripheral.dtb --iomem ~/quest3-iomem.txt --out-dtb ~/quest3-ram-first-boot.dtb > ~/quest3-layout-report.json

To update existing sources after inspecting the patch:

    git -C ~/quest-kexec apply --check "$PWD/loader-layout.patch"
    git -C ~/quest-kexec apply "$PWD/loader-layout.patch"
    q3make -j4 M="$HOME/quest-kexec/module" modules

Stop if --check fails; preserve your existing changes. A prebuilt module is
included for review, not an instruction to load or execute it. Do not use
execute=1, physical roundtrips or CPU shutdown tests with this package.

Validation: production C helper boundary/overflow/architecture tests; captured
map and DT reservation negative cases; new DT output changes only two chosen
properties and refuses overwrite; module build exit 0; binary CFI guards,
read-only preflight isolation and x18 stack frame checks passed.
