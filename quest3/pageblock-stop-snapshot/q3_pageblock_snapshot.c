// SPDX-License-Identifier: GPL-2.0-only
/* Experimental fixed-window metadata sample. Never reserves or migrates pages.
 * stop_machine pauses the system: explicit consent is required before loading.
 */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/ktime.h>
#include <linux/memory_hotplug.h>
#include <linux/mm.h>
#include <linux/mmzone.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pageblock-flags.h>
#include <linux/stop_machine.h>
#include <linux/string.h>
#include <linux/sysfs.h>

#define FIRST_PFN (0x90000000UL >> 12)
#define BLOCK_PAGES 1024UL
#define BLOCK_COUNT 13
#define CALLBACK_BUDGET_NS 1000000ULL

static bool sample;
module_param(sample, bool, 0000);
MODULE_PARM_DESC(sample, "Explicit opt-in to one system-wide stop_machine metadata sample");

struct block_record {
	unsigned long pfn;
	int type;
	bool reserved;
	char zone[16];
};

struct snapshot {
	struct block_record blocks[BLOCK_COUNT];
	u64 duration_ns;
	unsigned int completed;
};

static struct snapshot snapshot;
static struct kobject *report_kobj;
static char report[4096];

static int sample_heads(void *data)
{
	struct snapshot *result = data;
	u64 started = ktime_get_mono_fast_ns();
	unsigned int index;

	if (!irqs_disabled())
		return -EPERM;
	for (index = 0; index < BLOCK_COUNT; index++) {
		struct block_record *record = &result->blocks[index];
		unsigned long pfn = FIRST_PFN + index * BLOCK_PAGES;
		struct page *page;

		if (ktime_get_mono_fast_ns() - started > CALLBACK_BUDGET_NS)
			return -ETIMEDOUT;
		/* pfn_valid() alone does not establish initialized online metadata. */
		page = pfn_to_online_page(pfn);
		if (!page || is_zone_device_page(page))
			return -ERANGE;
		record->pfn = pfn;
		record->type = get_pageblock_migratetype(page);
		record->reserved = PageReserved(page);
		strscpy(record->zone, page_zone(page)->name, sizeof(record->zone));
		result->completed++;
	}
	result->duration_ns = ktime_get_mono_fast_ns() - started;
	return result->duration_ns > CALLBACK_BUDGET_NS ? -ETIMEDOUT : 0;
}

static ssize_t report_show(struct kobject *kobj, struct kobj_attribute *attr,
			   char *buffer)
{
	(void)kobj;
	(void)attr;
	return sysfs_emit(buffer, "%s", report);
}

static struct kobj_attribute report_attr = __ATTR(report, 0400, report_show, NULL);

static int __init q3_snapshot_init(void)
{
	size_t length = 0;
	unsigned int index;
	int ret;

	if (!sample)
		return -EACCES;
	if (!of_machine_is_compatible("qcom,anorak") ||
	    !of_machine_is_compatible("oculus,eureka"))
		return -ENODEV;
	if (PAGE_SHIFT != 12 || pageblock_order != 10)
		return -EOPNOTSUPP;
	memset(&snapshot, 0, sizeof(snapshot));
	/* Formatting, sysfs setup and printk occur only after CPUs resume. */
	ret = stop_machine(sample_heads, &snapshot, NULL);
	if (ret)
		return ret;
	if (snapshot.completed != BLOCK_COUNT)
		return -EIO;
	length += scnprintf(report + length, sizeof(report) - length,
		"heads_only=1 count=%u callback_ns=%llu all_pfns_checked=0 owned=0 dma_safe=0\n",
		snapshot.completed, (unsigned long long)snapshot.duration_ns);
	for (index = 0; index < BLOCK_COUNT; index++) {
		struct block_record *record = &snapshot.blocks[index];

		length += scnprintf(report + length, sizeof(report) - length,
			"block=0x%lx zone=%s migratetype=%d head_reserved=%u\n",
			record->pfn << PAGE_SHIFT, record->zone, record->type,
			record->reserved);
	}
	if (length >= sizeof(report) - 1)
		return -EOVERFLOW;
	report_kobj = kobject_create_and_add("q3_pageblock_snapshot", kernel_kobj);
	if (!report_kobj)
		return -ENOMEM;
	ret = sysfs_create_file(report_kobj, &report_attr.attr);
	if (ret) {
		kobject_put(report_kobj);
		report_kobj = NULL;
		return ret;
	}
	pr_info("q3_pageblock_snapshot: 13 head samples; CPUs resumed; no page allocation/migration, ownership or DMA claim\n");
	return 0;
}

static void __exit q3_snapshot_exit(void)
{
	sysfs_remove_file(report_kobj, &report_attr.attr);
	kobject_put(report_kobj);
}

module_init(q3_snapshot_init);
module_exit(q3_snapshot_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Experimental Quest 3 fixed-window pageblock head snapshot under stop_machine");
