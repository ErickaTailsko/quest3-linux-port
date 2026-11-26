#!/usr/bin/env python3
"""Pure draft contract/commitments. No I/O, native serializer or admission API.

Every envelope is execution_enabled=False and producer=host-contract-model.
SHA-256 links are not signatures or evidence that an action actually happened.
"""
import hashlib
import json
import re

PROFILE = 'q3-identity-query-host-draft-v3'
ROLES = ('check-environment', 'verify-identity-file', 'load-identity-module',
         'read-identity-report', 'unload-identity-module', 'remove-identity-file')
MAX_PLAN = 16384
MAX_ENVELOPE = 8192
MAX_CAPTURE = 65536
CONTEXT_KEYS = {'boot', 'attempt', 'device_binding_sha256', 'helper_sha256', 'module_sha256',
                'authorization_sha256', 'bootstrap_ack_sha256', 'stock_config_sha256', 'dtb_sha256',
                'kernel_release', 'module_bytes', 'root_dev', 'root_ino', 'lease_dev', 'lease_ino',
                'module_dev', 'module_ino'}


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)+'\n').encode('ascii')


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('duplicate envelope key')
        value[key] = item
    return value


def _decode(data, limit):
    if not isinstance(data, bytes) or not 0 < len(data) <= limit:
        raise ValueError('invalid/bounded canonical bytes required')
    try:
        value = json.loads(data, object_pairs_hook=_pairs)
        if not isinstance(value, dict) or _canonical(value) != data:
            raise ValueError('noncanonical envelope')
    except (RecursionError, UnicodeError, TypeError, OverflowError) as error:
        raise ValueError('invalid envelope encoding') from error
    return value


def _hex(value, length):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}', value):
        raise ValueError('invalid hex identifier/commitment')
    return value


def _integer(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('invalid integer/type')
    return value


def _hash(domain, data):
    return hashlib.sha256(b'ERIS-Q3-DRAFT-V3\0'+domain+b'\0'+data).hexdigest()


def _context(value):
    if not isinstance(value, dict) or set(value) != CONTEXT_KEYS:
        raise ValueError('unexpected/missing session context fields')
    if not isinstance(value['boot'], str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value['boot']):
        raise ValueError('invalid boot identity')
    _hex(value['attempt'], 32)
    for key in CONTEXT_KEYS:
        if key.endswith('sha256'):
            _hex(value[key], 64)
        elif key.endswith('_dev'):
            _integer(value[key], 0, (1 << 64)-1)
        elif key.endswith('_ino'):
            _integer(value[key], 1, (1 << 64)-1)
    if value['kernel_release'] != '5.10.246-gd7102a837402':
        raise ValueError('not the reviewed stock release')
    _integer(value['module_bytes'], 1, 1024*1024)
    if (len({value[key] for key in ('root_dev', 'lease_dev', 'module_dev')}) != 1 or
            len({value[key] for key in ('root_ino', 'lease_ino', 'module_ino')}) != 3):
        raise ValueError('private-file pins alias or cross filesystem')
    return dict(value)


def _action(context, role):
    file_args = dict(resource='identity-module', sha256=context['module_sha256'],
                     size=context['module_bytes'], device=context['module_dev'], inode=context['module_ino'])
    if role == 'check-environment':
        args = dict(kernel_release=context['kernel_release'], stock_config_sha256=context['stock_config_sha256'],
                    dtb_sha256=context['dtb_sha256'])
    elif role == 'verify-identity-file':
        args = file_args
    elif role == 'load-identity-module':
        args = dict(resource='identity-module', module='q3_cma_identity', inspect=True, attempt=context['attempt'])
    elif role == 'read-identity-report':
        args = dict(resource='identity-report', module='q3_cma_identity', attempt=context['attempt'])
    elif role == 'unload-identity-module':
        args = dict(module='q3_cma_identity', attempt=context['attempt'], ownership_resource='identity-report')
    elif role == 'remove-identity-file':
        args = dict(file_args, require_module_absent=True)
    else:
        raise ValueError('role outside fixed draft profile')
    return dict(role=role, arguments=args)


def _plan(context, operations, transports):
    context = _context(context)
    if (not isinstance(operations, (list, tuple)) or not isinstance(transports, (list, tuple)) or
            len(operations) != len(ROLES) or len(transports) != len(ROLES)):
        raise ValueError('exactly one nonce pair per fixed role required')
    nonces = [_hex(n, 32) for n in (*operations, *transports, context['attempt'])]
    if len(set(nonces)) != len(nonces):
        raise ValueError('operation/transport/attempt nonces must be distinct')
    return dict(schema=3, profile=PROFILE, execution_enabled=False, context=context,
                steps=[dict(sequence=i, operation=operations[i], transport_token=transports[i],
                            action=_action(context, role)) for i, role in enumerate(ROLES)])


def create_plan(context, operations, transports):
    """Construct a non-executable draft, NOT permission or a bootstrap ACK."""
    return _canonical(_plan(context, operations, transports))


def _parse_plan(data):
    value = _decode(data, MAX_PLAN)
    try:
        expected = _plan(value['context'], [s['operation'] for s in value['steps']],
                         [s['transport_token'] for s in value['steps']])
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('invalid plan shape') from error
    if _canonical(expected) != data:
        raise ValueError('role/order/typed arguments/schema differ from fixed draft')
    return value


def plan_commitment(plan):
    _parse_plan(plan)
    return _hash(b'PLAN', plan)


def _genesis(plan):
    value = _parse_plan(plan)
    return _hash(b'GENESIS', _canonical(dict(plan_sha256=plan_commitment(plan), context=value['context'])))


def initial_checkpoint(plan):
    return dict(completed_count=0, receipt_sha256=_genesis(plan))


def _claim(plan, sequence, predecessor):
    value = _parse_plan(plan)
    _integer(sequence, 0, len(ROLES)-1)
    step = value['steps'][sequence]
    return dict(schema=3, profile=PROFILE, producer='host-contract-model', execution_enabled=False,
                context_sha256=_hash(b'CONTEXT', _canonical(value['context'])), plan_sha256=plan_commitment(plan),
                sequence=sequence, operation=step['operation'], transport_token=step['transport_token'],
                action=step['action'], action_sha256=_hash(b'ACTION', _canonical(step['action'])),
                predecessor_receipt_sha256=_hex(predecessor, 64))


def _outcome(value):
    keys = {'kind', 'value', 'exec_errno', 'supervisor_interrupted',
            'stdout_size', 'stdout_sha256', 'stderr_size', 'stderr_sha256'}
    if not isinstance(value, dict) or set(value) != keys or type(value['supervisor_interrupted']) is not bool:
        raise ValueError('invalid outcome fields')
    _integer(value['exec_errno'], 0, 4095)
    if value['kind'] == 'exit':
        _integer(value['value'], 0, 255)
    elif value['kind'] == 'signal':
        _integer(value['value'], 1, 64)
        if value['exec_errno']:
            raise ValueError('signal outcome cannot be exec failure')
    else:
        raise ValueError('unknown outcome kind')
    if value['exec_errno'] and (value['kind'], value['value']) != ('exit', 127):
        raise ValueError('exec failure must bind exit 127')
    for stream in ('stdout', 'stderr'):
        _integer(value[stream+'_size'], 0, MAX_CAPTURE)
        _hex(value[stream+'_sha256'], 64)
        if value[stream+'_size'] == 0 and value[stream+'_sha256'] != hashlib.sha256(b'').hexdigest():
            raise ValueError('empty-stream digest mismatch')
    return dict(value)


def outcome_from_capture(kind, value, exec_errno, stdout, stderr, *, interrupted=False):
    """Commit supplied bytes; this function does NOT run, wait or authenticate a producer."""
    result = dict(kind=kind, value=value, exec_errno=exec_errno, supervisor_interrupted=interrupted)
    for stream, data in (('stdout', stdout), ('stderr', stderr)):
        if not isinstance(data, bytes) or len(data) > MAX_CAPTURE:
            raise ValueError('invalid/oversized supplied capture')
        result[stream+'_size'] = len(data)
        result[stream+'_sha256'] = hashlib.sha256(data).hexdigest()
    return _outcome(result)


def verify_capture(outcome, stdout, stderr):
    value = _outcome(outcome)
    expected = outcome_from_capture(value['kind'], value['value'], value['exec_errno'], stdout, stderr,
                                    interrupted=value['supervisor_interrupted'])
    if value != expected:
        raise ValueError('supplied bytes do not match committed streams')
    return True


def _receipt(claim_bytes, outcome):
    claim = _decode(claim_bytes, MAX_ENVELOPE)
    return dict(schema=3, profile=PROFILE, producer='host-contract-model', execution_enabled=False,
                context_sha256=claim['context_sha256'], plan_sha256=claim['plan_sha256'],
                sequence=claim['sequence'], operation=claim['operation'], transport_token=claim['transport_token'],
                claim_sha256=_hash(b'CLAIM', claim_bytes),
                predecessor_receipt_sha256=claim['predecessor_receipt_sha256'], outcome=_outcome(outcome))


def receipt_commitment(receipt):
    # Just a digest utility, not a promotion of an observed tail to a trusted checkpoint.
    value = _decode(receipt, MAX_ENVELOPE)
    if (type(value.get('schema')) is not int or value.get('schema') != 3 or value.get('profile') != PROFILE or
            value.get('execution_enabled') is not False or value.get('producer') != 'host-contract-model'):
        raise ValueError('not a draft receipt')
    return _hash(b'RECEIPT', receipt)


def _walk(plan, records):
    _parse_plan(plan)
    if not isinstance(records, (list, tuple)) or len(records) > len(ROLES):
        raise ValueError('bounded chain prefix required')
    predecessor, commitments, pending, stopped = _genesis(plan), [], False, False
    for sequence, pair in enumerate(records):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or pending or stopped:
            raise ValueError('record after unknown/pending/terminal outcome')
        claim, receipt = pair
        _decode(claim, MAX_ENVELOPE)
        if claim != _canonical(_claim(plan, sequence, predecessor)):
            raise ValueError('claim context/order/role/nonces/predecessor mismatch')
        if receipt is None:
            pending = True
            continue
        value = _decode(receipt, MAX_ENVELOPE)
        try:
            expected = _receipt(claim, value['outcome'])
        except KeyError as error:
            raise ValueError('receipt outcome missing') from error
        if receipt != _canonical(expected):
            raise ValueError('receipt does not commit this exact claim/outcome')
        predecessor = receipt_commitment(receipt)
        commitments.append(predecessor)
        outcome = value['outcome']
        stopped = (outcome['kind'], outcome['value'], outcome['exec_errno'], outcome['supervisor_interrupted']) != ('exit', 0, 0, False)
    return predecessor, commitments, pending, stopped


def build_claim(plan, completed_prefix):
    """Construct a draft only. No dispatcher, filesystem or next-action permit."""
    predecessor, _, pending, stopped = _walk(plan, completed_prefix)
    if pending or stopped or len(completed_prefix) == len(ROLES):
        raise ValueError('draft prefix cannot be extended')
    return _canonical(_claim(plan, len(completed_prefix), predecessor))


def build_receipt(plan, pending_prefix, outcome):
    _, _, pending, _ = _walk(plan, pending_prefix)
    if not pending:
        raise ValueError('last pending draft claim required')
    return _canonical(_receipt(pending_prefix[-1][0], outcome))


def verify_prefix(plan, expected_plan_sha256, records, checkpoint):
    """Check logical links against a caller-held plan/prefix anchor, not history.

    The caller must obtain checkpoint from its trusted durable local journal,
    NEVER by advancing it from the unacknowledged remote tail being checked.
    """
    if _hex(expected_plan_sha256, 64) != plan_commitment(plan):
        raise ValueError('caller-held plan anchor mismatch')
    _, commitments, pending, stopped = _walk(plan, records)
    if not isinstance(checkpoint, dict) or set(checkpoint) != {'completed_count', 'receipt_sha256'}:
        raise ValueError('explicit local checkpoint required')
    count = _integer(checkpoint['completed_count'], 0, len(commitments))
    anchor = commitments[count-1] if count else _genesis(plan)
    if _hex(checkpoint['receipt_sha256'], 64) != anchor:
        raise ValueError('caller-held acknowledged prefix commitment mismatch')
    state = ('claim-pending' if pending else 'terminal-outcome' if stopped else
             'draft-complete' if len(commitments) == len(ROLES) else 'draft-prefix')
    return dict(profile=PROFILE, state=state, logical_links_verified=True, local_checkpoint_matched=True,
                complete_receipts=len(commitments), anchored_receipts=count,
                unanchored_tail_receipts=len(commitments)-count,
                execution_enabled=False, authorization_verified=False, bootstrap_verified=False,
                historical_order_proven=False, tail_authenticity_verified=False,
                foreground_execution_verified=False, identity_report_verified=False,
                original_response_verified=False, publication_durability_verified=False,
                safe_to_mutate=False, replay_permitted=False, cleanup_permitted=False,
                automatic_resume_allowed=False, ownership_acquired=False, boot_ready=False)
