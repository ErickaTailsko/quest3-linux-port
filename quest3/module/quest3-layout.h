/* SPDX-License-Identifier: GPL-2.0 */
#ifndef QKX_QUEST3_LAYOUT_H
#define QKX_QUEST3_LAYOUT_H

#define QKX_LO 0x90000000ULL
#define QKX_HI 0x93400000ULL
#define QKX_INITRD 0x93000000ULL
#define QKX_DTB 0x93200000ULL

/* Board-specific supported offsets, from an aligned ARM64 boot base.
 * Bounds are checked before addition or page rounding. This does not reserve
 * destination RAM in the running kernel or authorize the final transition.
 */
static inline int qkx_image_layout(u64 offset, u64 size, u64 file_size,
				   u64 flags, u64 *entry)
{
	if ((offset != 0 && offset != 0x80000) || file_size < 64 ||
	    size < file_size || size > QKX_INITRD - QKX_LO - offset ||
	    (flags & 1) || !(flags & 8) ||
	    ((flags & 6) != 0 && (flags & 6) != 2))
		return -EINVAL;
	*entry = QKX_LO + offset;
	return 0;
}
#endif
