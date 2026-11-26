// SPDX-License-Identifier: GPL-2.0-only
/* Single default-CMA identity snapshot, never a payload allocator. */
#include <linux/cma.h>
#include <linux/dma-map-ops.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_reserved_mem.h>
#include <linux/string.h>
#include <linux/sysfs.h>

#if !defined(CONFIG_ARM64) || !defined(CONFIG_ARM64_4K_PAGES) || \
    !defined(CONFIG_CMA) || !defined(CONFIG_DMA_CMA) || \
    !defined(CONFIG_OF_RESERVED_MEM) || defined(CONFIG_OF_DYNAMIC) || \
    defined(CONFIG_OF_OVERLAY) || !defined(CONFIG_CFI_CLANG) || \
    defined(CONFIG_CFI_PERMISSIVE) || !defined(CONFIG_SHADOW_CALL_STACK) || \
    !defined(CONFIG_LTO_CLANG_FULL) || !defined(CONFIG_MODVERSIONS)
#error "Unsupported platform, lifetime configuration or protections"
#endif

/* Reviewed source layout only, not complete stock binary equivalence. */
static_assert(sizeof(struct reserved_mem) == 56);
static_assert(offsetof(struct reserved_mem, ops) == 24);
static_assert(offsetof(struct reserved_mem, base) == 32);
static_assert(offsetof(struct reserved_mem, size) == 40);
static_assert(offsetof(struct reserved_mem, priv) == 48);

struct identity_record {
	unsigned int stage;
	bool descriptor_valid;
	bool pointer_match;
	bool name_match;
	bool stable;
};

static struct identity_record record;
static struct kobject *report_kobj;
static char report[1024];
static bool inspect;
static char attempt[33];
module_param(inspect, bool, 0000);
module_param_string(attempt, attempt, sizeof(attempt), 0000);
MODULE_PARM_DESC(inspect, "Opt in to one default-CMA identity snapshot");
MODULE_PARM_DESC(attempt, "Required 32-character lowercase hex attempt identifier");

static int query_identity(struct identity_record *result)
{
	struct device_node *node;
	struct reserved_mem *rmem;
	struct cma *area;
	const char *name;
	u64 requested, base, size;
	int ret = -EINVAL;

	result->stage = 1;
	node = of_find_node_by_path("/reserved-memory/linux,cma");
	if (!node)
		return -ENOENT;
	result->stage = 2;
	if (!of_device_is_available(node) ||
	    !of_device_is_compatible(node, "shared-dma-pool") ||
	    !of_property_read_bool(node, "reusable") ||
	    !of_property_read_bool(node, "linux,cma-default") ||
	    of_property_read_bool(node, "no-map") ||
	    of_property_read_u64(node, "size", &requested) ||
	    requested != 32ULL * 1024 * 1024)
		goto put;
	result->stage = 3;
	rmem = of_reserved_mem_lookup(node);
	if (!rmem) {
		ret = -ENOENT;
		goto put;
	}
	base = READ_ONCE(rmem->base);
	size = READ_ONCE(rmem->size);
	if (!rmem->name || strncmp(rmem->name, "linux,cma", sizeof("linux,cma")) ||
	    !READ_ONCE(rmem->ops) || !base || size != 32ULL * 1024 * 1024)
		goto put;
	if ((base & (4ULL * 1024 * 1024 - 1)) ||
	    base > (1ULL << 32) - size) {
		ret = -ERANGE;
		goto put;
	}
	result->descriptor_valid = true;
	result->stage = 4;
	area = READ_ONCE(dma_contiguous_default_area);
	if (!area || READ_ONCE(rmem->priv) != area)
		goto put;
	result->pointer_match = true;
	result->stage = 5;
	/* Public accessor only, after equality; never access struct cma fields. */
	name = cma_get_name(area);
	if (!name || strncmp(name, "linux,cma", sizeof("linux,cma")))
		goto put;
	result->name_match = true;
	result->stage = 6;
	/* Consistency check, NOT a lifetime pin, hotplug lock or ABA proof. */
	if (READ_ONCE(dma_contiguous_default_area) != area ||
	    READ_ONCE(rmem->priv) != area) {
		ret = -EAGAIN;
		goto put;
	}
	result->stable = true;
	result->stage = 7;
	ret = 0;
put:
	of_node_put(node);
	return ret;
}

static ssize_t report_show(struct kobject *kobj, struct kobj_attribute *attr,
			   char *buffer)
{
	(void)kobj;
	(void)attr;
	return sysfs_emit(buffer, "%s", report);
}

static struct kobj_attribute report_attr = __ATTR(report, 0400, report_show, NULL);

static int __init q3_identity_init(void)
{
	unsigned int i;
	int error, ret, length;

	if (!inspect)
		return -EACCES;
	if (strlen(attempt) != 32)
		return -EINVAL;
	for (i = 0; i < 32; i++)
		if (!((attempt[i] >= '0' && attempt[i] <= '9') ||
		      (attempt[i] >= 'a' && attempt[i] <= 'f')))
			return -EINVAL;
	if (!of_machine_is_compatible("qcom,anorak") ||
	    !of_machine_is_compatible("oculus,eureka") || PAGE_SHIFT != 12)
		return -ENODEV;
	error = query_identity(&record);
	length = snprintf(report, sizeof(report),
		"schema=1 attempt=%s\n"
		"identity_observed=%u error=%d stage=%u descriptor_valid=%u "
		"pointer_match=%u name_match=%u stable=%u "
		"allocator_called=0 availability_proven=0 ownership_acquired=0 "
		"allocation_experiment_ready=0 boot_ready=0\n",
		attempt, !error, error, record.stage, record.descriptor_valid,
		record.pointer_match, record.name_match, record.stable);
	if (length < 0 || (size_t)length >= sizeof(report))
		return -EOVERFLOW;
	report_kobj = kobject_create_and_add("q3_cma_identity", kernel_kobj);
	if (!report_kobj)
		return -ENOMEM;
	ret = sysfs_create_file(report_kobj, &report_attr.attr);
	if (ret) {
		kobject_put(report_kobj);
		report_kobj = NULL;
	}
	return ret;
}

static void __exit q3_identity_exit(void)
{
	sysfs_remove_file(report_kobj, &report_attr.attr);
	kobject_put(report_kobj);
}

module_init(q3_identity_init);
module_exit(q3_identity_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Quest 3 default-CMA identity only; no payload allocation or handoff");
