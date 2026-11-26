# PMSG retention discriminator

Actual DT has separate pmsg-size 0x20000 and console-size 0x20000; stock config
PSTORE_PMSG=y. pmsg.c exposes a userspace write-only /dev/pmsg0. A small marker
through that character device exercises existing backend; no raw physical RAM
access, invented address or custom firmware command required.

The analyzed KernelCrash::for_each_ramoops generates console-ramoops-N and
dmesg-ramoops-N candidates. Its purge callback acts only on enumerated names.
No pmsg candidate was identified in this iterator. This does NOT exclude other
Android consumers or prove pmsg retention. Readback is via pstore after reboot,
not /dev/pmsg0 (which has no read implementation).

Use test -c before writing so missing node cannot be replaced by regular file.
A short marker consumes ring space; other log writers may overwrite it.
This is a diagnostic comparison to separate console cleanup from broader
retention failure. It is not a kernel callback logging transport: no exported
pstore PMSG writer was found and write_pmsg requires a userspace buffer. Do not
call it through kernel_write or use raw private function addresses.

Next device action: inspect /dev/pmsg0 and write one short unique marker,
record success. Then, if successful, one planned ordinary reboot and collect
pstore before any second full reboot. No need to alter crashreporter settings.
