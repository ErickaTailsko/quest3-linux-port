#!/usr/bin/env python3
"""Synthetic contract cases; no state-file writes, process or device action."""
import json
from pathlib import Path

import chain_v3_draft as m


context = dict(boot='00000000-0000-0000-0000-000000000001', attempt='a'*32,
               device_binding_sha256='0'*64, helper_sha256='1'*64, module_sha256='2'*64,
               authorization_sha256='3'*64, bootstrap_ack_sha256='4'*64,
               stock_config_sha256='5'*64, dtb_sha256='6'*64,
               kernel_release='5.10.246-gd7102a837402', module_bytes=280784,
               root_dev=1, root_ino=10, lease_dev=1, lease_ino=11, module_dev=1, module_ino=12)
operations = [f'{n:032x}' for n in range(1, 7)]
transports = [f'{n:032x}' for n in range(101, 107)]
plan = m.create_plan(context, operations, transports)
anchor = m.plan_commitment(plan)
initial = m.initial_checkpoint(plan)


def denied(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid draft/context/order/checkpoint accepted')


def verified(records, checkpoint=initial, active_plan=plan, expected_anchor=anchor):
    value = m.verify_prefix(active_plan, expected_anchor, records, checkpoint)
    assert value['logical_links_verified'] and value['local_checkpoint_matched']
    for key in ('execution_enabled', 'authorization_verified', 'bootstrap_verified',
                'historical_order_proven', 'tail_authenticity_verified', 'foreground_execution_verified',
                'identity_report_verified', 'original_response_verified', 'publication_durability_verified',
                'safe_to_mutate', 'replay_permitted', 'cleanup_permitted', 'automatic_resume_allowed',
                'ownership_acquired', 'boot_ready'):
        assert value[key] is False
    return value


def complete(prefix, index, output=None):
    claim = m.build_claim(plan, prefix)
    captured = (b'fixture-'+str(index).encode()) if output is None else output
    outcome = m.outcome_from_capture('exit', 0, 0, captured, b'')
    receipt = m.build_receipt(plan, [*prefix, (claim, None)], outcome)
    assert m.verify_capture(outcome, captured, b'')
    return [*prefix, (claim, receipt)]


assert verified([])['state'] == 'draft-prefix'
chain = []
for index, role in enumerate(m.ROLES):
    claim = m.build_claim(plan, chain)
    value = json.loads(claim)
    assert value['sequence'] == index and value['operation'] == operations[index]
    assert value['transport_token'] == transports[index] and value['action']['role'] == role
    expected_predecessor = initial['receipt_sha256'] if not chain else m.receipt_commitment(chain[-1][1])
    assert value['predecessor_receipt_sha256'] == expected_predecessor
    assert verified([*chain, (claim, None)])['state'] == 'claim-pending'
    denied(m.build_claim, plan, [*chain, (claim, None)])
    chain = complete(chain, index)
    assert verified(chain)['complete_receipts'] == index+1
assert verified(chain)['state'] == 'draft-complete'
denied(m.build_claim, plan, chain)
denied(m.build_receipt, plan, chain, m.outcome_from_capture('exit', 0, 0, b'', b''))

# Distinct domains: same canonical data cannot alias an intent/receipt/plan hash.
assert len({m._hash(domain, b'constant') for domain in (b'PLAN', b'CONTEXT', b'ACTION', b'CLAIM', b'RECEIPT', b'GENESIS')}) == 6

for index in range(len(chain)):
    checkpoint = dict(completed_count=index+1, receipt_sha256=m.receipt_commitment(chain[index][1]))
    value = verified(chain, checkpoint)
    assert value['anchored_receipts'] == index+1 and value['unanchored_tail_receipts'] == len(chain)-index-1
denied(m.verify_prefix, plan, 'f'*64, chain, initial)
for bad in (None, {}, dict(completed_count=True, receipt_sha256=initial['receipt_sha256']),
            dict(completed_count=7, receipt_sha256='f'*64), dict(completed_count=1, receipt_sha256='f'*64)):
    denied(m.verify_prefix, plan, anchor, chain, bad)

# Swapping/skipping/replaying claims or receipts cannot satisfy the fixed plan.
for bad in ([chain[1], chain[0]], [chain[1]], [chain[0], chain[0]],
            [(chain[0][0], chain[1][1])], [(chain[1][0], chain[0][1])],
            [(chain[0][0], None), chain[1]], chain+[chain[0]]):
    denied(m.verify_prefix, plan, anchor, bad, initial)
for field, replacement in (('sequence', True), ('operation', operations[1]), ('transport_token', transports[1]),
                            ('predecessor_receipt_sha256', 'f'*64), ('execution_enabled', True),
                            ('context_sha256', 'f'*64), ('schema', 2), ('producer', 'native-helper')):
    changed = json.loads(chain[0][0]); changed[field] = replacement
    denied(m.verify_prefix, plan, anchor, [(m._canonical(changed), chain[0][1])], initial)
for field, replacement in (('claim_sha256', 'f'*64), ('sequence', 0.0), ('execution_enabled', True),
                            ('predecessor_receipt_sha256', 'f'*64), ('plan_sha256', 'f'*64)):
    changed = json.loads(chain[0][1]); changed[field] = replacement
    denied(m.verify_prefix, plan, anchor, [(chain[0][0], m._canonical(changed))], initial)

# Every session binding changes the plan/genesis; old chain/anchor cannot follow.
changes = dict(boot='00000000-0000-0000-0000-000000000002', attempt='b'*32,
               device_binding_sha256='7'*64, helper_sha256='7'*64, module_sha256='7'*64,
               authorization_sha256='7'*64, bootstrap_ack_sha256='7'*64,
               stock_config_sha256='7'*64, dtb_sha256='7'*64, module_bytes=280785,
               root_ino=20, lease_ino=21, module_ino=22)
for key, value in changes.items():
    another = m.create_plan(dict(context, **{key: value}), operations, transports)
    assert m.plan_commitment(another) != anchor and m.initial_checkpoint(another) != initial
    denied(m.verify_prefix, another, anchor, chain, initial)
    denied(m.verify_prefix, another, m.plan_commitment(another), chain, m.initial_checkpoint(another))
for key, value in (('root_dev', True), ('module_bytes', False), ('module_bytes', 0),
                   ('module_bytes', 2**30), ('module_ino', context['lease_ino']),
                   ('module_dev', 2), ('root_ino', -1), ('lease_ino', 2**64),
                   ('kernel_release', 'quest-pro'), ('attempt', '../escape'),
                   ('module_sha256', 'UPPERCASE'), ('unexpected', 'shell command')):
    denied(m.create_plan, dict(context, **{key: value}), operations, transports)
denied(m.create_plan, context, operations[:-1], transports)
denied(m.create_plan, context, operations, operations)
denied(m.create_plan, context, [context['attempt'], *operations[1:]], transports)

# The plan cannot smuggle another role, resource, module, path, or boolean type.
for index, key, replacement in ((2, 'module', 'other-module'), (2, 'inspect', 1),
                                 (3, 'resource', '/proc/kcore'), (4, 'attempt', 'b'*32),
                                 (5, 'inode', context['lease_ino'])):
    changed = json.loads(plan); changed['steps'][index]['action']['arguments'][key] = replacement
    denied(m.plan_commitment, m._canonical(changed))
changed = json.loads(plan); changed['steps'][1], changed['steps'][2] = changed['steps'][2], changed['steps'][1]
denied(m.plan_commitment, m._canonical(changed))
for bad in (plan+b'\n', plan.replace(b'"schema":3', b'"schema":3,"schema":3'), b'x'*16385):
    denied(m.plan_commitment, bad)
legacy = m._canonical(dict(schema=2, intent={}, foreground_reaped=True, termination_kind='exit', termination_value=0))
denied(m.receipt_commitment, legacy)
denied(m.verify_prefix, plan, anchor, [(chain[0][0], legacy)], initial)
denied(m.verify_prefix, plan, anchor, [(chain[0][0], b'x'*8193)], initial)
bad_schema = json.loads(chain[0][1]); bad_schema['schema'] = 3.0
denied(m.receipt_commitment, m._canonical(bad_schema))

# Any unsuccessful/uncertain modeled outcome stops this normal profile. Cleanup
# after failure needs a distinct reviewed recovery decision, not a role skip.
for outcome in (m.outcome_from_capture('exit', 23, 0, b'', b'failure'),
                m.outcome_from_capture('signal', 15, 0, b'', b''),
                m.outcome_from_capture('exit', 127, 8, b'', b''),
                m.outcome_from_capture('exit', 0, 0, b'', b'', interrupted=True)):
    claim = m.build_claim(plan, [])
    receipt = m.build_receipt(plan, [(claim, None)], outcome)
    stopped = [(claim, receipt)]
    assert verified(stopped)['state'] == 'terminal-outcome'
    denied(m.build_claim, plan, stopped)
    denied(m.verify_prefix, plan, anchor, stopped+[chain[1]], initial)
denied(m.outcome_from_capture, 'exit', True, 0, b'', b'')
denied(m.outcome_from_capture, 'signal', 15, 8, b'', b'')
denied(m.outcome_from_capture, 'exit', 0, 8, b'', b'')
denied(m.outcome_from_capture, 'exit', 0, 0, b'x'*65537, b'')
denied(m.outcome_from_capture, 'exit', 0, 0, b'', b'', interrupted='yes')
captured = m.outcome_from_capture('exit', 0, 0, b'original', b'diagnostic')
denied(m.verify_capture, captured, b'other', b'diagnostic')
denied(m.verify_capture, captured, b'original', b'other')
bad_outcome = dict(captured, stdout_size=False)
denied(m.build_receipt, plan, [(chain[0][0], None)], bad_outcome)

# Crucial limit: an attacker can rewrite a complete unanchored suffix and
# recalculate public hashes. Logical consistency is NOT authentication/history.
rewritten = []
for index in range(len(m.ROLES)):
    rewritten = complete(rewritten, index, output=b'rewritten-output')
assert verified(rewritten)['unanchored_tail_receipts'] == 6
assert verified(rewritten)['tail_authenticity_verified'] is False
acknowledged = dict(completed_count=3, receipt_sha256=m.receipt_commitment(chain[2][1]))
denied(m.verify_prefix, plan, anchor, rewritten, acknowledged)
suffix = list(chain[:3])
for index in range(3, 6):
    suffix = complete(suffix, index, output=b'rewritten-tail')
assert verified(suffix, acknowledged)['unanchored_tail_receipts'] == 3
assert not verified(suffix, acknowledged)['historical_order_proven']

# Frozen synthetic vectors make canonical bytes/domains available for a future
# separately reviewed native implementation. Never regenerate them in a test.
vectors = json.loads(Path(__file__).with_name('v3-draft-vectors.json').read_text())
assert vectors['profile'] == m.PROFILE and vectors['execution_enabled'] is False
assert vectors['context'] == context and vectors['operations'] == operations and vectors['transports'] == transports
assert vectors['plan_canonical_ascii'].encode('ascii') == plan and vectors['plan_sha256'] == anchor
assert vectors['initial_checkpoint'] == initial and len(vectors['records']) == len(chain)
for vector, (claim, receipt) in zip(vectors['records'], chain):
    assert vector['claim_canonical_ascii'].encode('ascii') == claim
    assert vector['receipt_canonical_ascii'].encode('ascii') == receipt
    assert vector['receipt_sha256'] == m.receipt_commitment(receipt)
assert vectors['expected_complete_structure'] == verified(chain)

# Guard source scope: only data/commitment logic; no native/device side effects.
source = Path(m.__file__).read_text()
for forbidden in ('import os', 'import subprocess', 'import socket', 'open(', 'exec(', 'eval('):
    assert forbidden not in source
print('PASS v3 draft: typed fixed roles, context/plan/receipt chain, strict canonical data, local checkpoints, terminal/pending freeze; no execution/authentication claim')
