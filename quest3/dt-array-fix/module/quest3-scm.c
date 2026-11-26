// SPDX-License-Identifier: GPL-2.0
#include <linux/cpu.h>
#include <linux/errno.h>
#include <linux/of.h>
#include <linux/qcom_scm.h>
#include <linux/slab.h>
#include "quest3-scm.h"

struct qkx_core_reg {
	phys_addr_t address;
	u32 original;
	bool changed;
};

/* Older firmware describes a flat register list, without CPU phandles.
 * Report list entries rather than inventing a logical-CPU mapping. The DT
 * establishes addresses, not the writable bit semantics of that driver.
 */
static int qkx_core_hang_array_report(struct device_node *node, unsigned int mode)
{
	u32 *addresses, threshold, value;
	int count, i, j, ret;

	if (mode != 1) {
		pr_err("quest_kexec: core-hang config-arr schema is read-only; write ABI not verified\n");
		return -EOPNOTSUPP;
	}
	count = of_property_count_u32_elems(node, "qcom,config-arr");
	if (count <= 0 || count > nr_cpu_ids || count != num_possible_cpus() ||
	    of_property_count_u32_elems(node, "qcom,threshold-arr") != count)
		return -EINVAL;
	addresses = kcalloc(count, sizeof(*addresses), GFP_KERNEL);
	if (!addresses)
		return -ENOMEM;
	/* Validate the complete list before the first SCM read. */
	for (i = 0; i < count; i++) {
		ret = of_property_read_u32_index(node, "qcom,config-arr", i, &addresses[i]);
		if (ret)
			goto out;
		ret = of_property_read_u32_index(node, "qcom,threshold-arr", i, &threshold);
		if (ret)
			goto out;
		ret = -EINVAL;
		if (!addresses[i] || (addresses[i] & 3) || !threshold || (threshold & 3))
			goto out;
		for (j = 0; j < i; j++)
			if (addresses[j] == addresses[i])
				goto out;
	}
	for (i = 0; i < count; i++) {
		phys_addr_t address = addresses[i];

		ret = qcom_scm_io_readl(address, &value);
		if (ret)
			goto out;
		pr_info("quest_kexec: core-hang DT entry%d config=%pa value=%08x (read-only)\n",
			i, &address, value);
	}
	ret = 0;
out:
	kfree(addresses);
	return ret;
}

int qkx_core_hang_configure(unsigned int mode)
{
	struct device_node *node;
	struct of_phandle_args args;
	struct qkx_core_reg *regs;
	int cells, entries, i, j, cpu, ret = -ENODEV;

	if (!mode)
		return 0;
	if (mode > 2)
		return -EINVAL;

	if (!qcom_scm_is_available())
		return -ENODEV;
	node = of_find_compatible_node(NULL, NULL, "qcom,core-hang-detect");
	if (!node)
		return -ENODEV;
	if (!of_device_is_available(node))
		goto out_node;
	if (!of_find_property(node, "qcom,chd-percpu-info", NULL)) {
		ret = qkx_core_hang_array_report(node, mode);
		goto out_node;
	}
	cells = of_property_count_u32_elems(node, "qcom,chd-percpu-info");
	ret = -EINVAL;
	if (cells <= 0 || cells % 3)
		goto out_node;
	entries = cells / 3;
	regs = kcalloc(nr_cpu_ids, sizeof(*regs), GFP_KERNEL);
	if (!regs) {
		ret = -ENOMEM;
		goto out_node;
	}
	/* Same DT schema as drivers/soc/qcom/core_hang_detect.c. Validate the
	 * entire list before accessing firmware or changing any register.
	 */
	for (i = 0; i < entries; i++) {
		ret = of_parse_phandle_with_fixed_args(node, "qcom,chd-percpu-info",
						     2, i, &args);
		if (ret)
			goto out;
		cpu = of_cpu_node_to_id(args.np);
		of_node_put(args.np);
		if (cpu < 0 || cpu >= nr_cpu_ids || !cpu_possible(cpu))
			continue;
		ret = -EINVAL;
		if (!args.args[1] || (args.args[1] & 3) || regs[cpu].address)
			goto out;
		/* Different CPUs must not alias the same configuration register. */
		for (j = 0; j < nr_cpu_ids; j++)
			if (regs[j].address == args.args[1])
				goto out;
		regs[cpu].address = args.args[1];
	}
	for_each_possible_cpu(cpu) {
		ret = -EINVAL;
		if (!regs[cpu].address)
			goto out;
	}
	for_each_possible_cpu(cpu) {
		ret = qcom_scm_io_readl(regs[cpu].address, &regs[cpu].original);
		if (ret)
			goto out;
		pr_info("quest_kexec: core-hang cpu%d config=%pa value=%08x\n",
			cpu, &regs[cpu].address, regs[cpu].original);
	}
	if (mode == 2) {
		for_each_possible_cpu(cpu) {
			u32 value;

			if (!(regs[cpu].original & BIT(1)))
				continue;
			/* A failing write may have reached firmware: include it in rollback. */
			regs[cpu].changed = true;
			ret = qcom_scm_io_writel(regs[cpu].address,
						regs[cpu].original & ~BIT(1));
			if (ret)
				goto rollback;
			ret = qcom_scm_io_readl(regs[cpu].address, &value);
			if (ret)
				goto rollback;
			if (value != (regs[cpu].original & ~BIT(1))) {
				ret = -EIO;
				goto rollback;
			}
		}
	}
	ret = 0;
	goto out;
rollback:
	for_each_possible_cpu(cpu) {
		u32 restored;
		int err;

		if (!regs[cpu].changed)
			continue;
		err = qcom_scm_io_writel(regs[cpu].address, regs[cpu].original);
		if (!err)
			err = qcom_scm_io_readl(regs[cpu].address, &restored);
		if (!err && restored != regs[cpu].original)
			err = -EIO;
		if (err)
			pr_err("quest_kexec: core-hang rollback failed for cpu%d: %d\n", cpu, err);
	}
out:
	kfree(regs);
out_node:
	of_node_put(node);
	return ret;
}

int qkx_secure_watchdog_configure(unsigned int mode)
{
	int ret;

	if (!mode)
		return 0;
	if (mode > 2)
		return -EINVAL;
	/* Driver readiness is not a per-command firmware capability query. */
	if (!qcom_scm_is_available()) {
		pr_err("quest_kexec: SCM driver unavailable\n");
		return -ENODEV;
	}
	if (mode == 1) {
		pr_info("quest_kexec: SCM driver ready; secure-watchdog command not probed\n");
		return 0;
	}
	ret = qcom_scm_sec_wdog_deactivate();
	pr_info("quest_kexec: secure-watchdog deactivate returned %d\n", ret);
	return ret;
}
