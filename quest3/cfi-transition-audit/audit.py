#!/usr/bin/env python3
import re,json
from pathlib import Path
p=Path(__file__).resolve().parents[1]
s=(p/'module/loader.c').read_text()
exports={line.split()[1]:line.split()[0] for line in (p/'out/Module.symvers').read_text().splitlines()}
names=sorted(set(re.findall(r'lookup\("([^"]+)"\)',s)))
alternatives=['remove_cpu','add_cpu','stop_machine','kernel_restart','register_restart_handler','device_shutdown','freeze_processes','thaw_processes','smp_shutdown_nonboot_cpus','kernel_kexec']
result={'private_lookups':{n:exports.get(n) for n in names},'candidate_apis':{n:exports.get(n) for n in alternatives},'execute_enabled':False,'hardware_tested':False}
print(json.dumps(result,indent=2))
