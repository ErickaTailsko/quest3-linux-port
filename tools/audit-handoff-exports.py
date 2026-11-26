#!/usr/bin/env python3
"""Inventory source lookups against a supplied export table; never enables handoff."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ALTERNATIVES = ('kernel_restart', 'register_reboot_notifier', 'register_syscore_ops',
                'register_restart_handler', 'remove_cpu', 'add_cpu',
                'cpus_read_lock', 'cpus_read_unlock', 'cpu_hotplug_disable',
                'cpu_hotplug_enable', 'set_cpus_allowed_ptr', 'stop_machine',
                'alloc_contig_range', 'free_contig_range', 'request_resource',
                'device_shutdown', 'syscore_shutdown', 'kernel_kexec',
                'smp_send_stop', 'walk_iomem_res_desc')


def audit(loader, symvers):
    exports = {}
    for line in symvers.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 4 or not fields[3].startswith('EXPORT_SYMBOL'):
            raise ValueError('malformed Module.symvers entry')
        if fields[1] in exports:
            raise ValueError('duplicate exported symbol: ' + fields[1])
        exports[fields[1]] = {'export_type': fields[3], 'provider': fields[2]}
    if not exports:
        raise ValueError('empty export table')
    # This is a source inventory, including compiled-out historical paths.
    names = sorted(set(re.findall(r'\blookup\("([A-Za-z_][A-Za-z_0-9]*)"\)', loader)))
    def status(name):
        return {'symbol': name, 'exported': name in exports, **exports.get(name, {})}
    return {
        'scope': 'source references versus supplied exports, not compiled imports or live ABI proof',
        'private_lookup_count': len(names),
        'source_lookups': [status(name) for name in names],
        'nonexported_lookup_count': sum(name not in exports for name in names),
        'alternative_interfaces': [status(name) for name in ALTERNATIVES],
        'exported_does_not_mean_context_safe': True,
        'cfi_compatible_handoff_implemented': False,
        'execute_authorized': False,
    }


if __name__ == '__main__':
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loader', type=Path, default=repo / 'quest3/module/loader.c')
    parser.add_argument('--symvers', type=Path,
                        default=repo / 'quest3/inputs/quest3-llvm-config.bOyxO7/Module.symvers')
    args = parser.parse_args()
    try:
        loader, symvers = args.loader.read_bytes(), args.symvers.read_bytes()
        result = audit(loader.decode(), symvers.decode())
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + '\n')
    result['loader_sha256'] = hashlib.sha256(loader).hexdigest()
    result['supplied_symvers_sha256'] = hashlib.sha256(symvers).hexdigest()
    print(json.dumps(result, indent=2))
