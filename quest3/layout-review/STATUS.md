# Quest 3 layout review

Captured root iomem SHA256: 773fea1c2921d02146f4a1193730970415c4b487d5eed6dda69ae1cfa9f9ff57.
The window [0x90000000,0x93400000) is covered by System RAM [0x8e700000,0xd8000000)
and intersects no other resource listed in this capture. It also intersects no
reservation in the older private DTB available here. This is not a reservation
against Android page allocation/DMA and is not a guarantee about future boots.

Candidate Image offset=0, size=0x2b20000. Correct entry=0x90000000,
image end=0x92b20000, initrd=[0x93000000,0x9309145d), DTB base=0x93200000.
Loader now supports offset 0 and 0x80000 using bounded header-aware placement.
Old 0x80000 images retain entry 0x90080000. Source-page exclusion unchanged.

Module build exit 0; actual C helper boundary/overflow tests passed; linked CFI
guards, preflight dispatch and x18 disassembly checks passed. Offline verifier
rejects nested iomem/DT reservations, truncated and oversized inputs; optional
new DT copy changes only /chosen linux,initrd-start/end and refuses overwrite.
The newer user-generated USB DTB is not present here: run verifier locally on it.

Pending: review target bootargs, destination ownership/DMA quiescence, complete
CFI-safe handoff, and reliable retained diagnostics. No device stage or boot
performed. execute=1 remains blocked under CFI. Public package excludes all DTBs
and device diagnostic captures.
