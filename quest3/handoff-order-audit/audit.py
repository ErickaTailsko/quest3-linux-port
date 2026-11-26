#!/usr/bin/env python3
from pathlib import Path
import json,re
p=Path(__file__).resolve().parents[1]
k=p/'kernel'
exports={l.split()[1] for l in (p/'out/Module.symvers').read_text().splitlines()}
s=(k/'kernel/kexec_core.c').read_text(); start=s.index('int kernel_kexec(void)'); s=s[start:]
sequence=['kernel_restart_prepare(NULL)','migrate_to_reboot_cpu()','cpu_hotplug_enable()','machine_shutdown()','machine_kexec(kexec_image)']
# Comments can mention calls: use statement-only matches.
positions=[re.search(r'^\s*'+re.escape(x)+r';',s,re.M).start() for x in sequence]
assert positions==sorted(positions)
critical=['kernel_restart_prepare','device_shutdown','device_block_probing','migrate_to_reboot_cpu','machine_shutdown','cpu_hotplug_enable','bus_for_each_dev']
r={'native_order':sequence,'exports':{x:x in exports for x in critical},'manual_shutdown_equivalence_proven':False,'DMA_quiescence_proven':False,'hardware_tested':False}
print(json.dumps(r,indent=2))
