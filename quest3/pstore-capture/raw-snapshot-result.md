# First target raw ramoops snapshot

Snapshot size 589824, SHA256 d72f71f0b58cd848bc400c1b4f02833bf13b0daed3934d28ee517e94408423f1;
manifest and independent local hash agree. Boot ID 5b9eb78c-0c06-4bbb-91d6-f2d2d289ad98.
User confirmed module insert 0, full 36-block collection verified, module unload 0.

Zones: dmesg 0x30000 bytes empty/zero body; console 0x20000 bytes full (131060
valid bytes, start128090); ftrace 0x20000 bytes empty/zero body; pmsg 0x20000
bytes with valid start=size=2726. No old console or PMSG marker was found in
logical or raw data. Console contains current-boot text. This does not prove
firmware clearing: even a short new pmsg stream could overwrite an old marker
near the start of a cleared-index ring. Late raw snapshot alone remains inconclusive.

Next distinct test: standard /dev/pmsg0 API, unique token after 64KiB padding,
then verified same-boot baseline confirming exactly one marker in upper half
of the PMSG data region, followed by a separately planned normal-reboot paired
read. No kernel reserved-memory writer or new logging backend is introduced.
The preparation scripts do not reboot or install modules. A lost response never
retries the PMSG write; baseline bytes decide whether the write actually landed.
