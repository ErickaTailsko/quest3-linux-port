/* SPDX-License-Identifier: GPL-2.0-only */
/* Arithmetic-only reference. NOT included by the active loader.
 * No allocator, PFN/ownership/lifetime validation, DT parser or execution API.
 * Caller retains responsibility for Image/DT bytes, handles and boot context.
 */
#ifndef Q3_RETURNED_LAYOUT_CORE_H
#define Q3_RETURNED_LAYOUT_CORE_H

#ifdef Q3RL_HOST_TEST
#include <stdint.h>
#include <errno.h>
typedef uint64_t q3rl_u64;
#else
#include <linux/types.h>
#include <linux/errno.h>
typedef u64 q3rl_u64;
#endif

#define Q3RL_PAGE 4096ULL
#define Q3RL_ALIGN (2ULL << 20)
#define Q3RL_GIB (1ULL << 30)
#define Q3RL_PHYS_LIMIT (1ULL << 48)
#define Q3RL_IMAGE_MAX (32ULL << 20)
#define Q3RL_SLOT_COUNT 3U

enum q3rl_role { Q3RL_IMAGE = 0, Q3RL_INITRD = 1, Q3RL_DTB = 2 };
enum q3rl_provider { Q3RL_DEFAULT_CMA_LABEL = 1, Q3RL_BUDDY_LABEL = 2 };

struct q3rl_allocation {
	unsigned int role, provider;
	q3rl_u64 start, bytes;
};

struct q3rl_request {
	q3rl_u64 image_file_bytes, image_offset, image_size, image_flags;
	q3rl_u64 initrd_file_bytes, dtb_file_bytes;
	unsigned int slot_count;
	struct q3rl_allocation slots[Q3RL_SLOT_COUNT];
};

struct q3rl_segment {
	q3rl_u64 allocation_start, allocation_end, allocation_bytes;
	q3rl_u64 payload_start, file_bytes, file_end;
	q3rl_u64 stage_bytes, stage_end, zero_tail_bytes, copy_pages;
};

struct q3rl_geometry {
	struct q3rl_segment slots[Q3RL_SLOT_COUNT];
	q3rl_u64 image_entry, dtb_address, initrd_start, initrd_end;
	q3rl_u64 window_start, window_end, window_bytes, total_request_bytes;
	unsigned int geometry_only, ownership_acquired, boot_ready;
};

/* Outputs remain untouched on ALL errors, including NULL/invalid input. */
static inline int q3rl_range_end(q3rl_u64 start, q3rl_u64 bytes,
			       q3rl_u64 *end)
{
	if (!end || start >= Q3RL_PHYS_LIMIT || !bytes ||
	    bytes > Q3RL_PHYS_LIMIT - start)
		return -ERANGE;
	*end = start + bytes;
	return 0;
}

static inline int q3rl_round_up(q3rl_u64 value, q3rl_u64 alignment,
			      q3rl_u64 *rounded)
{
	if (!rounded || !alignment || (alignment & (alignment - 1)) ||
	    value > ~(q3rl_u64)0 - (alignment - 1))
		return -ERANGE;
	*rounded = (value + alignment - 1) & ~(alignment - 1);
	return 0;
}

static inline int q3rl_intersects(q3rl_u64 a, q3rl_u64 a_end,
				 q3rl_u64 b, q3rl_u64 b_end)
{
	return a < b_end && b < a_end;
}

static inline int q3rl_validate_geometry(const struct q3rl_request *in,
					struct q3rl_geometry *out)
{
	struct q3rl_geometry result = { 0 };
	const struct q3rl_allocation *a;
	struct q3rl_segment *s;
	q3rl_u64 image_stage, image_request, required, first, last, span;
	q3rl_u64 files[Q3RL_SLOT_COUNT], stages[Q3RL_SLOT_COUNT];
	unsigned int i, j, role, mask = 0, provider;
	int ret;

	if (!in || !out || in->slot_count != Q3RL_SLOT_COUNT)
		return -EINVAL;
	if (in->image_file_bytes < 64 || in->image_file_bytes > in->image_size ||
	    in->image_size > Q3RL_IMAGE_MAX ||
	    (in->image_offset != 0 && in->image_offset != 0x80000ULL) ||
	    (in->image_flags != 8 && in->image_flags != 10) ||
	    !in->initrd_file_bytes || in->initrd_file_bytes > Q3RL_ALIGN ||
	    in->dtb_file_bytes < 40 || in->dtb_file_bytes > Q3RL_ALIGN)
		return -EINVAL;
	ret = q3rl_round_up(in->image_size, Q3RL_PAGE, &image_stage);
	if (ret)
		return ret;
	if (image_stage > Q3RL_IMAGE_MAX ||
	    in->image_offset > Q3RL_IMAGE_MAX - image_stage)
		return -ERANGE;
	ret = q3rl_round_up(in->image_offset + image_stage, Q3RL_ALIGN,
			    &image_request);
	if (ret || image_request > Q3RL_IMAGE_MAX)
		return -ERANGE;
	files[Q3RL_IMAGE] = in->image_file_bytes;
	files[Q3RL_INITRD] = in->initrd_file_bytes;
	files[Q3RL_DTB] = in->dtb_file_bytes;
	stages[Q3RL_IMAGE] = image_stage;
	ret = q3rl_round_up(in->initrd_file_bytes, Q3RL_PAGE,
			    &stages[Q3RL_INITRD]);
	if (ret)
		return ret;
	ret = q3rl_round_up(in->dtb_file_bytes, Q3RL_PAGE, &stages[Q3RL_DTB]);
	if (ret)
		return ret;
	for (i = 0; i < Q3RL_SLOT_COUNT; ++i) {
		a = &in->slots[i];
		role = a->role;
		if (role >= Q3RL_SLOT_COUNT || (mask & (1U << role)))
			return -EINVAL;
		mask |= 1U << role;
		provider = role == Q3RL_IMAGE ? Q3RL_DEFAULT_CMA_LABEL : Q3RL_BUDDY_LABEL;
		required = role == Q3RL_IMAGE ? image_request : Q3RL_ALIGN;
		if (a->provider != provider || a->bytes != required ||
		    !a->start || a->start % Q3RL_ALIGN)
			return -EINVAL;
		s = &result.slots[role];
		s->allocation_start = a->start;
		s->allocation_bytes = a->bytes;
		ret = q3rl_range_end(a->start, a->bytes, &s->allocation_end);
		if (ret)
			return ret;
		s->payload_start = a->start;
		if (role == Q3RL_IMAGE)
			s->payload_start += in->image_offset;
		s->file_bytes = files[role];
		s->stage_bytes = stages[role];
		ret = q3rl_range_end(s->payload_start, s->stage_bytes, &s->stage_end);
		if (ret || s->stage_end > s->allocation_end)
			return -ERANGE;
		s->file_end = s->payload_start + s->file_bytes;
		s->zero_tail_bytes = s->stage_bytes - s->file_bytes;
		s->copy_pages = s->stage_bytes / Q3RL_PAGE;
		/* Requests are bounded above by 32 + 2 + 2 MiB. */
		result.total_request_bytes += a->bytes;
	}
	for (i = 0; i < Q3RL_SLOT_COUNT; ++i)
		for (j = i + 1; j < Q3RL_SLOT_COUNT; ++j)
			if (q3rl_intersects(result.slots[i].allocation_start,
				result.slots[i].allocation_end,
				result.slots[j].allocation_start,
				result.slots[j].allocation_end))
				return -EINVAL;
	result.image_entry = result.slots[Q3RL_IMAGE].payload_start;
	result.dtb_address = result.slots[Q3RL_DTB].payload_start;
	result.initrd_start = result.slots[Q3RL_INITRD].payload_start;
	result.initrd_end = result.slots[Q3RL_INITRD].file_end;
	first = result.image_entry < result.initrd_start ?
		result.image_entry : result.initrd_start;
	last = result.slots[Q3RL_IMAGE].stage_end > result.slots[Q3RL_INITRD].stage_end ?
		result.slots[Q3RL_IMAGE].stage_end : result.slots[Q3RL_INITRD].stage_end;
	result.window_start = first & ~(Q3RL_GIB - 1);
	span = last - result.window_start;
	ret = q3rl_round_up(span, Q3RL_GIB, &result.window_bytes);
	if (ret || result.window_bytes > 32 * Q3RL_GIB)
		return -ERANGE;
	ret = q3rl_range_end(result.window_start, result.window_bytes,
			    &result.window_end);
	if (ret)
		return ret;
	result.geometry_only = 1;
	/* ownership_acquired and boot_ready intentionally remain zero. */
	*out = result;
	return 0;
}

/* DATA-ONLY intersection mask over FULL allocations, including all padding.
 * Zero mask means only "not in these destinations", NOT "safe/owned/free".
 * Caller may query source pages, descriptors, page tables or scratch ranges;
 * this routine does not acquire, map, read or free any of those resources.
 */
static inline int q3rl_destination_overlap_mask(const struct q3rl_request *in,
		q3rl_u64 start, q3rl_u64 bytes, unsigned int *out_mask)
{
	struct q3rl_geometry geometry;
	q3rl_u64 end;
	unsigned int i, mask = 0;
	int ret;

	if (!out_mask)
		return -EINVAL;
	ret = q3rl_validate_geometry(in, &geometry);
	if (ret)
		return ret;
	ret = q3rl_range_end(start, bytes, &end);
	if (ret)
		return ret;
	for (i = 0; i < Q3RL_SLOT_COUNT; ++i)
		if (q3rl_intersects(start, end, geometry.slots[i].allocation_start,
				    geometry.slots[i].allocation_end))
			mask |= 1U << i;
	*out_mask = mask;
	return 0;
}

#endif /* Q3_RETURNED_LAYOUT_CORE_H */
