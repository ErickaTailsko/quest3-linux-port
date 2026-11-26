# Static analysis of supplied libovr_crashreporter.so

Build ID supplied: 8b22a8b5939d171f76aaa307741a4e03.
No binary modified or executed. Addresses below are ELF virtual addresses.

KernelCrash vtable at 0x146cb8; object vptr address point 0x146cc8:
slot +16 = for_each_ramoops (0xc4380)
slot +24 = purgePstoreDirectory (0xc48e0)
slot +40 = hasKernelPanicImpl (0xc4ea0)
slot +56 = collectFromPstoreImpl (0xc5200).

hasKernelPanicImpl enumerates available ramoops nodes; its lambda 0xc64b0
sets a boolean when an enumerated file exists. The method name alone does
NOT mean that it checked the content for a panic phrase.
CrashReporter::collectKernelCrash calls HasKernelPanic at 0xb0570; false
branches to cleanup/return 0xb0a9c. True eventually invokes CollectFromPstore
at 0xb079c.

collectFromPstoreImpl calls dmesgHasPanicPhrase at 0xc54b0. False branches
0xc54b4 -> 0xc5a3c; log message at VA 0x5177a explicitly drops non-panic
report. Further diagnostics format the drop reason (string at 0x52f3c).
This branch joins 0xc5e88; 0xc5ea4 loads vtable slot +24 and 0xc5ea8
invokes purgePstoreDirectory. The valid-report path also invokes that slot
at 0xc54f0 after successful addFileWithContent. Not all error exits purge.

purgePstoreDirectory constructs a per-file callback with vtable at 0x146d18
and uses slot +16 for enumeration. The callback at 0xc6240 calls remove@plt
at 0xc6264, reporting failures if remove returns nonzero.

Conclusion: this binary can remove non-panic pstore logs, without keeping
a normal kernel-panic report. This establishes an actual code path, not
proof that the path ran during the user's marker reboot. RAM retention,
early boot record availability and other consumers remain unobserved.
A post-root empty pstore cannot distinguish firmware loss from this cleanup.

No supported preserve-non-panic setting was established. The observed
crash-reporter-pstore-dir-name config key selects the directory; it is not
a demonstrated preserve toggle. Do not change it speculatively or fabricate
a panic phrase. Need collection before sys.boot_completed triggers -k,
or independently validated persistent transport. Early-root hook availability
must be established with the Singularity setup before installing boot scripts.
