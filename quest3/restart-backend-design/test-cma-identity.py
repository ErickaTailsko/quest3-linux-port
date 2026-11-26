#!/usr/bin/env python3
"""Synthetic identity/ordering/cleanup checks; no kernel or ADB operations."""
from cma_identity_model import IdentityQuery, MIB


class FakeIdentity:
    def __init__(self):
        self.events = []
        self.node = object()
        self.area = object()
        self.valid = True
        self.name = 'linux,cma'
        self.descriptor = dict(name='linux,cma', base=0x40000000, size=32*MIB,
                               ops_present=True, priv=self.area)
        self.defaults = [self.area, self.area]
        self.final_priv = self.area

    def find_node(self, path):
        self.events.append('find')
        assert path == '/reserved-memory/linux,cma'
        return self.node

    def node_valid(self, node):
        assert node is self.node
        self.events.append('properties')
        return self.valid

    def lookup(self, node):
        assert node is self.node
        self.events.append('lookup')
        return self.descriptor

    def default_area(self):
        self.events.append('default')
        return self.defaults.pop(0)

    def get_name(self, area):
        assert area is self.area and area is self.descriptor['priv']
        self.events.append('name')
        return self.name

    def descriptor_priv(self, descriptor):
        assert descriptor is self.descriptor
        self.events.append('priv_recheck')
        return self.final_priv

    def put_node(self, node):
        assert node is self.node
        self.events.append('put')


gates = dict(consent=True, platform=True, abi=True, static_lifetime=True)


def run(api, **overrides):
    query = IdentityQuery()
    result = query.run(api, **{**gates, **overrides})
    assert all(result[key] is False for key in (
        'allocator_called', 'availability_proven', 'ownership_acquired',
        'allocation_experiment_ready', 'boot_ready'))
    if api.node is not None and api.events:
        assert api.events[-1] == 'put' and api.events.count('put') == 1
    before = list(api.events)
    try:
        query.run(api, **gates)
    except ValueError:
        pass
    else:
        raise AssertionError('query was repeatable')
    assert before == api.events
    return result


for gate in gates:
    for denied in (False, None, 1, 'yes'):
        api = FakeIdentity()
        assert not run(api, **{gate: denied})['identity_observed']
        assert not api.events
api = FakeIdentity()
assert run(api)['identity_observed']
assert api.events == ['find', 'properties', 'lookup', 'default', 'name',
                      'default', 'priv_recheck', 'put']
api = FakeIdentity(); api.node = None
assert run(api)['reason'] == 'node_missing' and api.events == ['find']
api = FakeIdentity(); api.valid = False
assert run(api)['reason'] == 'node_invalid' and 'lookup' not in api.events
api = FakeIdentity(); api.descriptor = None
assert run(api)['reason'] == 'descriptor_missing'
for key, value in [('name', 'display'), ('size', 16*MIB), ('ops_present', False),
                   ('base', 0), ('base', -4*MIB), ('base', 0x40001000),
                   ('base', (1 << 32) - 4*MIB), ('base', True)]:
    api = FakeIdentity(); api.descriptor[key] = value
    assert run(api)['reason'] == 'descriptor_invalid'
    assert 'default' not in api.events and 'name' not in api.events
for default, priv in [(None, object()), (object(), None), (object(), object())]:
    api = FakeIdentity(); api.defaults[0] = default; api.descriptor['priv'] = priv
    assert run(api)['reason'] == 'pointer_mismatch_or_null' and 'name' not in api.events
api = FakeIdentity(); api.name = 'other'
assert run(api)['reason'] == 'name_mismatch'
for changed in ('default', 'priv'):
    api = FakeIdentity()
    if changed == 'default':
        api.defaults[1] = object()
    else:
        api.final_priv = object()
    assert run(api)['reason'] == 'identity_changed'
print('PASS CMA identity model: one shot, fail closed, pointer-before-name, node cleanup; no runtime proof')
