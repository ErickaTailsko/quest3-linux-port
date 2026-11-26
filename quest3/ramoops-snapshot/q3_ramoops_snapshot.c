// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/io.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include <linux/sizes.h>
#include <linux/crc32.h>

/* Read-only copy of the existing DT-described ramoops reservation. No address
 * parameter, private driver structure, hardware write or reboot registration.
 * The mapping uses the same cache attributes as stock ram_core.c, mem-type=0.
 * This is a best-effort live snapshot, not a locked or crash-consistent image.
 */
static void *snapshot;
static size_t snapshot_size;
static struct kobject *snapshot_kobj;

static ssize_t q3_snapshot_read(struct file *file, struct kobject *kobj,
			       struct bin_attribute *attr, char *buf,
			       loff_t off, size_t count)
{
	if (off < 0)
		return -EINVAL;
	if (off >= snapshot_size)
		return 0;
	count = min_t(size_t, count, snapshot_size - off);
	memcpy(buf, (char *)snapshot + off, count);
	return count;
}

static struct bin_attribute snapshot_attr = {
	.attr = { .name = "data", .mode = 0400 },
	.read = q3_snapshot_read,
};

static int q3_copy_region(phys_addr_t start, size_t size)
{
	struct page **pages;
	void *mapped;
	void __iomem *iomapped;
	unsigned int i, count = size >> PAGE_SHIFT;
	bool valid = pfn_valid(PHYS_PFN(start));

	/* Mixed mappings and non-reserved normal RAM are not accepted. */
	for (i = 0; i < count; i++) {
		unsigned long pfn = PHYS_PFN(start) + i;

		if (!!pfn_valid(pfn) != valid)
			return -EINVAL;
		if (valid && !PageReserved(pfn_to_page(pfn)))
			return -EPERM;
	}
	if (!valid) {
		/* Same non-PFN mapping and attributes as persistent_ram_iomap().
		 * The existing ramoops driver retains ownership of the reservation.
		 */
		iomapped = ioremap_wc(start, size);
		if (!iomapped)
			return -ENOMEM;
		memcpy_fromio(snapshot, iomapped, size);
		iounmap(iomapped);
		return 0;
	}
	pages = kmalloc_array(count, sizeof(*pages), GFP_KERNEL);
	if (!pages)
		return -ENOMEM;
	for (i = 0; i < count; i++)
		pages[i] = pfn_to_page(PHYS_PFN(start) + i);
	mapped = vmap(pages, count, VM_MAP | VM_IOREMAP,
		      pgprot_writecombine(PAGE_KERNEL));
	kfree(pages);
	if (!mapped)
		return -ENOMEM;
	memcpy_fromio(snapshot, (void __iomem *)mapped, size);
	vunmap(mapped);
	return 0;
}

static int __init q3_snapshot_init(void)
{
	struct device_node *node, *parent;
	struct platform_device *pdev;
	struct resource resource;
	u32 memtype = 0;
	int ret, reg_len;

	if (!of_machine_is_compatible("qcom,anorak") ||
	    !of_machine_is_compatible("oculus,eureka"))
		return -ENODEV;
	node = of_find_compatible_node(NULL, NULL, "ramoops");
	if (!node)
		return -ENODEV;
	parent = of_find_node_by_path("/reserved-memory");
	if (!parent || node->parent != parent ||
	    !of_device_is_available(node) ||
	    !of_get_property(node, "reg", &reg_len) || reg_len != 16) {
		ret = -EINVAL;
		goto put_node;
	}
	if (of_find_property(node, "mem-type", NULL) &&
	    of_property_read_u32(node, "mem-type", &memtype)) {
		ret = -EINVAL;
		goto put_node;
	}
	if (memtype != 0) {
		ret = -EOPNOTSUPP;
		goto put_node;
	}
	ret = of_address_to_resource(node, 0, &resource);
	if (ret)
		goto put_node;
	snapshot_size = resource_size(&resource);
	if (resource.end < resource.start || !snapshot_size || snapshot_size > SZ_1M ||
	    !IS_ALIGNED(resource.start, PAGE_SIZE) ||
	    !IS_ALIGNED(snapshot_size, PAGE_SIZE)) {
		ret = -EINVAL;
		goto put_node;
	}
	pdev = of_find_device_by_node(node);
	if (!pdev) {
		ret = -ENODEV;
		goto put_node;
	}
	device_lock(&pdev->dev);
	if (!pdev->dev.driver || strcmp(pdev->dev.driver->name, "ramoops")) {
		ret = -ENODEV;
		goto unlock_device;
	}
	snapshot = vzalloc(snapshot_size);
	if (!snapshot) {
		ret = -ENOMEM;
		goto unlock_device;
	}
	ret = q3_copy_region(resource.start, snapshot_size);
unlock_device:
	device_unlock(&pdev->dev);
	put_device(&pdev->dev);
put_node:
	of_node_put(parent);
	of_node_put(node);
	if (ret)
		goto free_snapshot;
	snapshot_kobj = kobject_create_and_add("q3_ramoops_snapshot", kernel_kobj);
	if (!snapshot_kobj) {
		ret = -ENOMEM;
		goto free_snapshot;
	}
	snapshot_attr.size = snapshot_size;
	ret = sysfs_create_bin_file(snapshot_kobj, &snapshot_attr);
	if (ret) {
		kobject_put(snapshot_kobj);
		goto free_snapshot;
	}
	pr_info("q3_ramoops_snapshot: readonly copy bytes=%zu crc32=%08x; no reboot or reserved-memory writes; live snapshot may race writers\n",
		snapshot_size, crc32_le(0, snapshot, snapshot_size));
	return 0;
free_snapshot:
	vfree(snapshot);
	snapshot = NULL;
	return ret;
}

static void __exit q3_snapshot_exit(void)
{
	sysfs_remove_bin_file(snapshot_kobj, &snapshot_attr);
	kobject_put(snapshot_kobj);
	vfree(snapshot);
}
module_init(q3_snapshot_init);
module_exit(q3_snapshot_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only DT-bounded Quest 3 ramoops forensic snapshot");
