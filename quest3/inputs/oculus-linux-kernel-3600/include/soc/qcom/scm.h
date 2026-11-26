/* SPDX-License-Identifier: GPL-2.0 */
/* Minimal compat header: declarations only.
 * quest-kexec resolves the real implementations via kallsyms_lookup_name()
 * at runtime (see lookup() in loader.c) -- nothing here is linked.
 * Struct layout mirrors the long-stable Qualcomm downstream legacy SCM ABI.
 */
#ifndef __MACH_SCM_H
#define __MACH_SCM_H

#include <linux/types.h>

#define SCM_SVC_BOOT 0x1
#define SCM_SVC_PIL 0x2
#define SCM_SVC_UTIL 0x3
#define SCM_SVC_TZ 0x4
#define SCM_SVC_IO 0x5
#define SCM_SVC_INFO 0x6
#define SCM_SVC_SSD 0x7

#define SCM_SIP_FNID(s, c) (((((s) & 0xFF) << 8) | ((c) & 0xFF)) | 0x02000000)

#define MAX_SCM_ARGS 10
#define MAX_SCM_RETS 3

enum scm_arg_types {
SCM_VAL,
SCM_RO,
SCM_RW,
SCM_BUFVAL,
};

#define SCM_ARGS_IMPL(num, a, b, c, d, e, f, g, h, i, j, ...) ((((a) & 0xff) << 4) | (((b) & 0xff) << 6) | (((c) & 0xff) << 8) | (((d) & 0xff) << 10) | (((e) & 0xff) << 12) | (((f) & 0xff) << 14) | (((g) & 0xff) << 16) | (((h) & 0xff) << 18) | (((i) & 0xff) << 20) | (((j) & 0xff) << 22) | (num & 0xffff))

#define SCM_ARGS(...) SCM_ARGS_IMPL(__VA_ARGS__, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

struct scm_desc {
u32 arginfo;
u64 args[MAX_SCM_ARGS];
u64 ret[MAX_SCM_RETS];

/* private */
void *extra_arg_buf;
u64 x5;
};

extern u32 scm_io_read(phys_addr_t address);
extern int scm_io_write(phys_addr_t address, u32 val);
extern int scm_call2(u32 cmd_id, struct scm_desc *desc);
extern int scm_is_call_available(u32 svc_id, u32 cmd_id);

#endif
