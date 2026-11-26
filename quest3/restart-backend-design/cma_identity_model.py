#!/usr/bin/env python3
"""One-shot identity design model with fake objects, never a device collector."""
from dataclasses import dataclass


MIB = 1024 * 1024


@dataclass
class IdentityQuery:
    state: str = 'NEW'

    def run(self, api, *, consent, platform, abi, static_lifetime):
        if self.state != 'NEW':
            raise ValueError('query cannot be repeated, including after failure')
        self.state = 'REJECTED'
        result = dict(identity_observed=False, allocator_called=False,
                      availability_proven=False, ownership_acquired=False,
                      allocation_experiment_ready=False, boot_ready=False)
        if not all(value is True for value in (consent, platform, abi, static_lifetime)):
            result['reason'] = 'preflight'
            return result
        node = api.find_node('/reserved-memory/linux,cma')
        if node is None:
            result['reason'] = 'node_missing'
            return result
        try:
            # Includes exact path, shared-dma-pool, reusable, no no-map,
            # linux,cma-default, available node and the expected DT size.
            if not api.node_valid(node):
                result['reason'] = 'node_invalid'
                return result
            descriptor = api.lookup(node)
            if descriptor is None:
                result['reason'] = 'descriptor_missing'
                return result
            if (descriptor['name'] != 'linux,cma' or
                    descriptor['size'] != 32 * MIB or
                    not descriptor['ops_present'] or
                    type(descriptor['base']) is not int or
                    descriptor['base'] <= 0 or
                    descriptor['base'] % (4 * MIB) or
                    descriptor['base'] + descriptor['size'] > 1 << 32):
                result['reason'] = 'descriptor_invalid'
                return result
            area = api.default_area()
            if area is None or descriptor['priv'] is None or area is not descriptor['priv']:
                result['reason'] = 'pointer_mismatch_or_null'
                return result
            # Do not call even the name accessor on a mismatched pointer.
            if api.get_name(area) != 'linux,cma':
                result['reason'] = 'name_mismatch'
                return result
            # Re-observation catches some inconsistencies, NOT an ABA/lifetime lock.
            if api.default_area() is not area or api.descriptor_priv(descriptor) is not area:
                result['reason'] = 'identity_changed'
                return result
            result['identity_observed'] = True
            result['reason'] = 'matched_snapshot_only'
            self.state = 'OBSERVED'
            return result
        finally:
            api.put_node(node)
