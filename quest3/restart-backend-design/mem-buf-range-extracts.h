/* SPDX-License-Identifier: GPL-2.0-only */
/* Reviewed function extracts from kernel revision dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f.
 * kernel/resource.c: Copyright (C) 1999 Linus Torvalds;
 * Copyright (C) 1999 Martin Mares <mj@ucw.cz>.
 * mem-buf-dev.c: Copyright (c) 2020-2021, The Linux Foundation. All rights reserved.
 * Host-test fixture only. Bodies retain source behavior; comments/spacing abbreviated.
 */

static struct resource * __request_resource(struct resource *root, struct resource *new)
{
	resource_size_t start = new->start;
	resource_size_t end = new->end;
	struct resource *tmp, **p;

	if (end < start)
		return root;
	if (start < root->start)
		return root;
	if (end > root->end)
		return root;
	p = &root->child;
	for (;;) {
		tmp = *p;
		if (!tmp || tmp->start > end) {
			new->sibling = tmp;
			*p = new;
			new->parent = root;
			return NULL;
		}
		p = &tmp->sibling;
		if (tmp->end < start)
			continue;
		return tmp;
	}
}

struct resource * __request_region(struct resource *parent,
				   resource_size_t start, resource_size_t n,
				   const char *name, int flags)
{
	DECLARE_WAITQUEUE(wait, current);
	struct resource *res = alloc_resource(GFP_KERNEL);
	struct resource *orig_parent = parent;

	if (!res)
		return NULL;
	res->name = name;
	res->start = start;
	res->end = start + n - 1;
	write_lock(&resource_lock);
	for (;;) {
		struct resource *conflict;

		res->flags = resource_type(parent) | resource_ext_type(parent);
		res->flags |= IORESOURCE_BUSY | flags;
		res->desc = parent->desc;
		conflict = __request_resource(parent, res);
		if (!conflict)
			break;
		if (conflict->desc == IORES_DESC_DEVICE_PRIVATE_MEMORY) {
			pr_warn("Unaddressable device %s %pR conflicts with %pR",
				conflict->name, conflict, res);
		}
		if (conflict != parent) {
			if (!(conflict->flags & IORESOURCE_BUSY)) {
				parent = conflict;
				continue;
			}
		}
		if (conflict->flags & flags & IORESOURCE_MUXED) {
			add_wait_queue(&muxed_resource_wait, &wait);
			write_unlock(&resource_lock);
			set_current_state(TASK_UNINTERRUPTIBLE);
			schedule();
			remove_wait_queue(&muxed_resource_wait, &wait);
			write_lock(&resource_lock);
			continue;
		}
		free_resource(res);
		res = NULL;
		break;
	}
	write_unlock(&resource_lock);
	if (res && orig_parent == &iomem_resource)
		revoke_devmem(res);
	return res;
}

int mem_buf_map_mem_s1(struct gh_sgl_desc *sgl_desc)
{
	u64 base, size;
	int i, ret;

	for (i = 0; i < sgl_desc->n_sgl_entries; i++) {
		base = sgl_desc->sgl_entries[i].ipa_base;
		size = sgl_desc->sgl_entries[i].size;
		ret = add_memory_subsection(numa_node_id(), base, size);
		if (ret) {
			pr_err("%s: failed to add memory base=%llx, size=%llx, ret=%d\n",
				__func__, base, size, ret);
			goto out;
		}
	}
	return 0;
out:
	for (i--; i >= 0; i--) {
		base = sgl_desc->sgl_entries[i].ipa_base;
		size = sgl_desc->sgl_entries[i].size;
		remove_memory_subsection(numa_node_id(), base, size);
	}
	return ret;
}

int mem_buf_unmap_mem_s1(struct gh_sgl_desc *sgl_desc)
{
	u64 base, size;
	int i, ret = 0;

	for (i = 0; i < sgl_desc->n_sgl_entries; i++) {
		base = sgl_desc->sgl_entries[i].ipa_base;
		size = sgl_desc->sgl_entries[i].size;
		ret = remove_memory_subsection(numa_node_id(), base, size);
		if (ret)
			pr_err("%s: failed to remove memory base=%llx, size=%llx\n, ret=%d\n",
				__func__, base, size, ret);
	}
	return ret;
}
