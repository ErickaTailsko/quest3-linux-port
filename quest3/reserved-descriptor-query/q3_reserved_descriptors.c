// SPDX-License-Identifier: GPL-2.0-only
/* One fixed-list descriptor query. No PFNs, contents, callbacks or page acquisition. */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_reserved_mem.h>
#include <linux/string.h>
#include <linux/sysfs.h>

#if !defined(CONFIG_ARM64) || !defined(CONFIG_OF_RESERVED_MEM) || \
    defined(CONFIG_OF_DYNAMIC) || defined(CONFIG_OF_OVERLAY)
#error "Unsupported descriptor lifetime/architecture configuration"
#endif

/* This is a reviewed source ABI, not proof of stock binary equivalence. */
static_assert(sizeof(struct reserved_mem) == 56);
static_assert(offsetof(struct reserved_mem, ops) == 24);
static_assert(offsetof(struct reserved_mem, base) == 32);
static_assert(offsetof(struct reserved_mem, size) == 40);
static_assert(offsetof(struct reserved_mem, priv) == 48);

struct expected_region {
	const char *name;
	u64 size;
	u64 lower;
	u64 upper;
};

#define MIB (1024ULL * 1024)
#define LOW_REGION(name, mib) { name, (mib) * MIB, 0, 0xffffffffULL }
static const struct expected_region expected[] = {
	LOW_REGION("linux,cma", 32),
	LOW_REGION("user_contig_region", 16),
	LOW_REGION("qseecom_region", 20),
	LOW_REGION("qseecom_ta_region", 16),
	LOW_REGION("cdsp_eva_region", 4),
	LOW_REGION("adsp_heap_region", 12),
	LOW_REGION("secure_cdsp_region", 40),
	LOW_REGION("sp_region", 16),
	{ "va_md_mem_region", 16 * MIB, 0x100000000ULL, 0xffffffffffffffffULL },
	LOW_REGION("audio_cma_region", 16),
	LOW_REGION("non_secure_display_region", 164),
	LOW_REGION("cnss_wlan_region", 32),
	LOW_REGION("mem_dump_region", 12),
};

struct region_record {
	u64 base;
	u64 size;
	bool ops_present;
	bool priv_present;
	int error;
};

static struct region_record records[ARRAY_SIZE(expected)];
static struct kobject *report_kobj;
static char report[4096];
static bool inspect;
module_param(inspect, bool, 0000);
MODULE_PARM_DESC(inspect, "Opt in to one fixed-list reserved-memory descriptor query");

static int validate_record(const struct expected_region *spec,
			   const struct region_record *record)
{
	if (!record->base || record->size != spec->size ||
	    !record->ops_present || !record->priv_present)
		return -EINVAL;
	if (record->base & (4 * MIB - 1))
		return -ERANGE;
	if (record->base > U64_MAX - record->size ||
	    record->base < spec->lower || record->base + record->size > spec->upper)
		return -ERANGE;
	return 0;
}

static int query_one(const struct expected_region *spec, struct region_record *record)
{
	struct device_node *node;
	struct reserved_mem *rmem;
	char path[96];
	u64 requested;
	int ret;

	scnprintf(path, sizeof(path), "/reserved-memory/%s", spec->name);
	node = of_find_node_by_path(path);
	if (!node)
		return -ENOENT;
	ret = -EINVAL;
	if (!of_device_is_available(node) ||
	    !of_device_is_compatible(node, "shared-dma-pool") ||
	    !of_property_read_bool(node, "reusable") ||
	    of_property_read_bool(node, "no-map") ||
	    of_property_read_u64(node, "size", &requested) || requested != spec->size)
		goto put;
	rmem = of_reserved_mem_lookup(node);
	if (!rmem) {
		ret = -ENOENT;
		goto put;
	}
	if (!rmem->name || strcmp(rmem->name, spec->name))
		goto put;
	record->base = READ_ONCE(rmem->base);
	record->size = READ_ONCE(rmem->size);
	record->ops_present = READ_ONCE(rmem->ops) != NULL;
	record->priv_present = READ_ONCE(rmem->priv) != NULL;
	ret = validate_record(spec, record);
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

static int __init q3_descriptors_init(void)
{
	unsigned int i, j, complete = 0;
	size_t length = 0;
	int ret;

	if (!inspect)
		return -EACCES;
	if (!of_machine_is_compatible("qcom,anorak") ||
	    !of_machine_is_compatible("oculus,eureka") || PAGE_SHIFT != 12)
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(expected); i++)
		records[i].error = query_one(&expected[i], &records[i]);
	/* Reject overlap even when the individual descriptors appear consistent. */
	for (i = 0; i < ARRAY_SIZE(expected); i++) {
		for (j = i + 1; j < ARRAY_SIZE(expected); j++) {
			if (validate_record(&expected[i], &records[i]) ||
			    validate_record(&expected[j], &records[j]))
				continue;
			if (records[i].base < records[j].base + records[j].size &&
			    records[j].base < records[i].base + records[i].size) {
				records[i].error = -EEXIST;
				records[j].error = -EEXIST;
			}
		}
		if (!records[i].error)
			complete++;
	}
	length += scnprintf(report + length, sizeof(report) - length,
		"descriptors_only=1 count=13 complete=%u owned=0 dma_safe=0 cpu_pause=0\n",
		complete);
	for (i = 0; i < ARRAY_SIZE(expected); i++)
		length += scnprintf(report + length, sizeof(report) - length,
			"name=%s base=0x%llx size=0x%llx ops=%u priv=%u error=%d\n",
			expected[i].name, (unsigned long long)records[i].base,
			(unsigned long long)records[i].size, records[i].ops_present,
			records[i].priv_present, records[i].error);
	if (length >= sizeof(report) - 1)
		return -EOVERFLOW;
	report_kobj = kobject_create_and_add("q3_reserved_descriptors", kernel_kobj);
	if (!report_kobj)
		return -ENOMEM;
	ret = sysfs_create_file(report_kobj, &report_attr.attr);
	if (ret) {
		kobject_put(report_kobj);
		report_kobj = NULL;
	}
	return ret;
}

static void __exit q3_descriptors_exit(void)
{
	sysfs_remove_file(report_kobj, &report_attr.attr);
	kobject_put(report_kobj);
}

module_init(q3_descriptors_init);
module_exit(q3_descriptors_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Quest 3 fixed-list reserved-memory descriptor query; no page acquisition");
