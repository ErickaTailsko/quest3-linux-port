# Runtime review of the supplied sources

This build reproduces the supplied source. Compilation and CRC checks do not establish successful module loading or a safe hardware handoff. No device has been accessed from this environment.

## Confirmed: x18 is not restored by the reversible relocation test

module/transition.S sets x18 from x4 in qkx_reloc_start. Both the one-page relocation test in qkx_test_transition and qkx_test_full_copy enter that copied relocation code via qkx_roundtrip. qkx_roundtrip saves/restores x19-x28 and x30, but not x18. After returning from the copied relocation code, x18 still contains the cookie passed as x4. With CONFIG_SHADOW_CALL_STACK=y the kernel reserves x18 as the shadow-stack pointer. A subsequent instrumented call/return can therefore access an invalid shadow-stack address. The short physical probe itself does not clobber x18, but the following relocation rehearsal does.

The reversible trampoline must preserve/restore x18 before test_transition or test_full_copy is exercised. The current build deliberately does not change the supplied assembly. The existing 96-byte frame has room for an additional saved register, but any source change needs its own build and review.

## Confirmed: bus_find_device_by_name is an inline helper

include/linux/device/bus.h defines bus_find_device_by_name as static inline and implements it using bus_find_device and device_match_name. The supplied loader attempts lookup("bus_find_device_by_name") and returns -ENOENT if it cannot resolve it. A source-level inline helper must not be assumed to be available by that standalone symbol name. Use the actual supported helper/API in a source correction.

## Confirmed: legacy SCM interface differs from the matching kernel headers

The supplied compatibility header declares scm_io_read, scm_io_write, scm_is_call_available and scm_call2 with struct scm_desc. The public kernel headers instead expose qcom_scm_io_readl(phys_addr_t, unsigned int *), qcom_scm_io_writel and qcom_scm_sec_wdog_deactivate. Its internal qcom_scm_desc also has a different layout and a separate qcom_scm_res. Renaming symbols or casting pointers is insufficient. The core-hang and secure-watchdog modes must not be considered ported by virtue of successful compilation.

## Confirmed: watchdog preservation and USB power-state paths remain incomplete

The supplied loader assigns wdt_regs=NULL in the preserve_watchdog branch and immediately returns -ENOMEM. Its DWC3 in_lpm local value is hardcoded to zero with a TODO. Earlier uploaded tools/run.sh enables execute=1 and preserve_watchdog=1 by default. Those defaults are not validated for these sources.

## Requires further validation: calls through addresses obtained using kprobes/kallsyms

qkx_resolve stores kp.addr in a function pointer after probing kallsyms_lookup_name. The module is instrumented with strict cross-DSO CFI. Such an address is not automatically a CFI-valid indirect-call target merely because the declared C prototype looks correct. The same issue applies to further addresses returned by lookup. Compiler-generated CFI entry points and the actual accepted targets must be checked before module loading; do not disable CFI to mask a rejected call.

## Source identity limitation

The public source commit is dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f. The device reports internal release suffix gd7102a837402. Matching configuration, compiler, release text and local symbol CRCs do not prove equivalence to that private source revision or to all installed device modules.
