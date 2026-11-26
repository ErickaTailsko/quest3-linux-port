// SPDX-License-Identifier: GPL-2.0-only
/* Read page metadata only; fixed reviewed Quest 3 window, no acquisition. */
#include <linux/init.h>
#include <linux/mm.h>
#include <linux/mmzone.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/pageblock-flags.h>

#define Q3_START 0x90000000UL
#define Q3_END   0x93400000UL

/* Root-readable, immutable after init; no addresses are accepted as parameters.
 * An insertion-time report value is ignored and overwritten before sampling.
 */
static char report[4096];
module_param_string(report, report, sizeof(report), 0400);
MODULE_PARM_DESC(report, "Read-only sampled pageblock metadata; insertion value ignored");

static const char *migration_name(int type)
{
	switch (type) {
	case MIGRATE_UNMOVABLE: return "UNMOVABLE";
	case MIGRATE_MOVABLE: return "MOVABLE";
	case MIGRATE_RECLAIMABLE: return "RECLAIMABLE";
	case MIGRATE_HIGHATOMIC: return "HIGHATOMIC";
#ifdef CONFIG_CMA
	case MIGRATE_CMA: return "CMA";
#endif
#ifdef CONFIG_MEMORY_ISOLATION
	case MIGRATE_ISOLATE: return "ISOLATE";
#endif
	default: return "UNKNOWN";
	}
}

static int __init q3_window_init(void)
{
	unsigned long first = Q3_START >> PAGE_SHIFT;
	unsigned long end = Q3_END >> PAGE_SHIFT;
	unsigned long block, pfn;
	struct zone *range_zone = NULL;
	unsigned int total_reserved = 0;
	size_t length = 0;
	bool same_zone = true, types_eligible = true, types_uniform = true;
	int range_type = -1;

	if (!of_machine_is_compatible("qcom,anorak") ||
	    !of_machine_is_compatible("oculus,eureka"))
		return -ENODEV;
	/* Stock enables hot-remove, but its export table lacks get_online_mems/
	 * put_online_mems. Do not race metadata teardown or use private symbols.
	 * This deliberately refuses the present stock configuration.
	 */
	if (IS_ENABLED(CONFIG_MEMORY_HOTPLUG)) {
		pr_err("q3_ram_window_probe: metadata lifetime lock not established for hotplug memory; refusing\n");
		return -EOPNOTSUPP;
	}
	if (PAGE_SHIFT != 12 || pageblock_order != 10 ||
	    first % pageblock_nr_pages || end % pageblock_nr_pages)
		return -EOPNOTSUPP;
	/* Validate every PFN before dereferencing page or zone metadata. */
	for (pfn = first; pfn < end; pfn++) {
		if (!pfn_valid(pfn) || is_zone_device_page(pfn_to_page(pfn)))
			return -ERANGE;
	}
	length += scnprintf(report + length, sizeof(report) - length,
		"window=0x%lx-0x%lx page_shift=%u pageblock_order=%u atomic=0 owned=0 dma_safe=0\n",
		Q3_START, Q3_END, (unsigned int)PAGE_SHIFT,
		(unsigned int)pageblock_order);
	for (block = first; block < end; block += pageblock_nr_pages) {
		struct page *head = pfn_to_page(block);
		struct zone *zone = page_zone(head);
		unsigned int reserved = 0;
		int before = get_pageblock_migratetype(head), after;
		bool block_zone = true;

		if (!range_zone)
			range_zone = zone;
		if (range_type < 0)
			range_type = before;
		for (pfn = block; pfn < block + pageblock_nr_pages; pfn++) {
			struct page *page = pfn_to_page(pfn);

			block_zone &= page_zone(page) == zone;
			reserved += PageReserved(page) ? 1 : 0;
		}
		after = get_pageblock_migratetype(head);
		same_zone &= block_zone && zone == range_zone;
		types_uniform &= before == range_type && before == after;
		types_eligible &= before == MIGRATE_MOVABLE;
#ifdef CONFIG_CMA
		/* CMA is a distinct ownership regime: report but never acquire it. */
		if (before == MIGRATE_CMA)
			types_eligible = false;
#endif
		total_reserved += reserved;
		length += scnprintf(report + length, sizeof(report) - length,
			"block=0x%lx zone=%s one_zone=%u type_before=%s type_after=%s reserved=%u\n",
			block << PAGE_SHIFT, zone->name, block_zone,
			migration_name(before), migration_name(after), reserved);
	}
	length += scnprintf(report + length, sizeof(report) - length,
		"summary same_zone=%u sampled_uniform=%u movable_only=%u reserved=%u allocation_feasible=unknown\n",
		same_zone, types_uniform, types_eligible, total_reserved);
	/* No operation uses these observations to allocate, isolate or migrate. */
	if (length >= sizeof(report) - 1)
		return -EOVERFLOW;
	pr_info("q3_ram_window_probe: sampled 13 pageblocks; RO metadata only, live/racy, no reservation or DMA claim\n");
	return 0;
}

static void __exit q3_window_exit(void)
{
	pr_info("q3_ram_window_probe: unloaded; no window pages acquired or released\n");
}

module_init(q3_window_init);
module_exit(q3_window_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Quest 3 fixed-window read-only pageblock metadata probe");
