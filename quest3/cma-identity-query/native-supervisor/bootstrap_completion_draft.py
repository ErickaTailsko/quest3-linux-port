#!/usr/bin/env python3
"""Pure bootstrap completion/checkpoint contract; no I/O or admission API.

Supplied wait/boot/capture observations are NOT authenticated by this model.
Checkpoint creation computes bytes only: it never persists or trusts an anchor.
The caller-held anchor for restart review must come from outside the tail under
review. No existing journal, observer, controller or native writer uses this API.
"""
import base64
import hashlib
import re

import bootstrap_receipt as b
from transport_protocol import parse as parse_completion

PROFILE = 'q3-bootstrap-completion-host-draft-v1'
LIMIT = 100000
MAX_STDERR = 65536


def flags():
    return dict(execution_enabled=False, admission_enabled=False, pin_import_permitted=False,
                local_pin_ack_verified=False, bootstrap_verified=False, authorization_verified=False,
                transport_history_verified=False, publication_durability_verified=False,
                replay_permitted=False, cleanup_permitted=False, automatic_resume_allowed=False,
                safe_to_mutate=False, controller_integrated=False)


def _hex(value, size=64):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(size)+'}',value):
        raise ValueError('invalid commitment/nonce')
    return value


def _hash(role,data):
    return hashlib.sha256(b'ERIS-Q3-BOOTSTRAP-COMPLETION-DRAFT-V1\0'+role+b'\0'+data).hexdigest()


def _record(kind, **fields):
    return b.canonical(dict(schema=1,profile=PROFILE,producer='host-contract-model',
                            kind=kind,**fields,**flags()))


def _pins(values, count):
    if (not isinstance(values,(list,tuple)) or len(values)!=count or
            any(type(v) is not int or not 0<=v<1<<64 for v in values) or
            any(not values[i] for i in range(1,count,2)) or
            len(set(values[::2]))!=1 or len(set(values[1::2]))!=count//2):
        raise ValueError('distinct same-filesystem typed pins required')
    return list(values)


def create_pending(request, transport_token, local_journal_intent_sha256, local_journal_pins):
    """Data that must be durably committed BEFORE dispatch in a future protocol."""
    value=b.parse_request(request)
    _hex(transport_token,32)
    if transport_token in (value['attempt'],value['bootstrap_operation']):
        raise ValueError('attempt/operation/transport nonces must differ')
    return _record('pending',request=value,request_sha256=b.request_commitment(request),
                   transport_token=transport_token,local_journal_intent_sha256=_hex(local_journal_intent_sha256),
                   local_journal_pins=_pins(local_journal_pins,6),role='bootstrap-metadata-only')


def _pending(data):
    value=b._parse(data,LIMIT)
    try:
        expected=create_pending(b.canonical(value['request']),value['transport_token'],
                                value['local_journal_intent_sha256'],value['local_journal_pins'])
    except (KeyError,TypeError) as error:
        raise ValueError('pending shape mismatch') from error
    if expected!=data: raise ValueError('pending profile/context/canonical fields mismatch')
    return value


def pending_commitment(data):
    _pending(data)
    return _hash(b'PENDING',data)


def create_completion(pending, receipt, wire, stderr, *, boot_samples, transport):
    """Check supplied capture/context, NOT the truth of wait/transport observations.

    A frame alone or local exit zero alone is insufficient. Failure/timeout,
    interruption, unreaped foreground, incomplete streams or boot change cannot
    produce a completion draft. Nothing retries, reads a peer or runs cleanup.
    """
    value=_pending(pending); request=b.canonical(value['request'])
    expected_transport=dict(kind='exit',returncode=0,foreground_reaped=True,
                            streams_complete=True,interrupted=False)
    if (not isinstance(transport,dict) or b.canonical(transport)!=b.canonical(expected_transport)):
        raise ValueError('unknown/failed/incomplete local transport outcome')
    boot=value['request']['boot']
    if not isinstance(boot_samples,(tuple,list)) or list(boot_samples)!=[boot,boot]:
        raise ValueError('two matching supplied boot samples required')
    if not isinstance(stderr,bytes) or len(stderr)>MAX_STDERR:
        raise ValueError('bounded stderr capture required')
    reply,status=parse_completion(wire,value['transport_token'])
    if status!=0: raise ValueError('remote bootstrap failed or guard rejected')
    parsed=b.parse_receipt(receipt,request)
    b.reply_matches(reply,request,parsed['receipt_sha256'])
    return _record('completion',pending_sha256=pending_commitment(pending),
        request_sha256=value['request_sha256'],receipt=b._parse(receipt,4096),
        receipt_sha256=parsed['receipt_sha256'],candidate_pins=parsed['candidate_pins'],
        transport=expected_transport,boot_samples=[boot,boot],wire_ascii=wire.decode('ascii'),
        stderr_b64=base64.b64encode(stderr).decode('ascii'),stderr_size=len(stderr),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),remote_status=0,
        reply_sha256=hashlib.sha256(reply).hexdigest())


def _completion(pending, data):
    value=b._parse(data,LIMIT)
    try:
        expected=create_completion(pending,b.canonical(value['receipt']),value['wire_ascii'].encode('ascii'),
            base64.b64decode(value['stderr_b64'],validate=True),boot_samples=value['boot_samples'],
            transport=value['transport'])
    except (KeyError,TypeError,UnicodeError) as error:
        raise ValueError('completion shape/encoding mismatch') from error
    if expected!=data: raise ValueError('completion context/fields/capture mismatch')
    return value


def completion_commitment(pending, data):
    _completion(pending,data)
    return _hash(b'COMPLETION',data)


def create_checkpoint_draft(pending, completion, local_ack_sha256):
    """Compute an anchor proposal; NOT a durable write or a trust decision.

    A future caller must independently persist/anchor it. Reading this proposal
    from the same unconfirmed tail cannot establish successful ACK publication.
    """
    p=_pending(pending); c=_completion(pending,completion)
    return _record('checkpoint',pending_sha256=pending_commitment(pending),
        completion_sha256=completion_commitment(pending,completion),
        local_ack_sha256=_hex(local_ack_sha256),receipt_sha256=c['receipt_sha256'],
        candidate_pins=c['candidate_pins'],local_journal_pins=p['local_journal_pins'])


def checkpoint_commitment(pending, completion, checkpoint):
    value=b._parse(checkpoint,LIMIT)
    try: expected=create_checkpoint_draft(pending,completion,value['local_ack_sha256'])
    except KeyError as error: raise ValueError('checkpoint missing ACK commitment') from error
    if expected!=checkpoint: raise ValueError('checkpoint context/fields mismatch')
    return _hash(b'CHECKPOINT',checkpoint)


def review_restart(pending, completion, checkpoint, *, caller_checkpoint_sha256,
                   observed_ack_sha256, observed_local_journal_pins, observed_peer_pins,
                   boot_sample):
    """Logical comparison under an INDEPENDENT caller-held anchor; never resume.

    This function has no filesystem/transport API. The provenance/durability of
    the supplied external anchor and samples remain obligations of the caller.
    A match cannot authorize commands, upgrade a fixture journal or recover a
    live checkpoint in HostAckJournal.
    """
    p=_pending(pending); c=_completion(pending,completion)
    anchor=checkpoint_commitment(pending,completion,checkpoint)
    if _hex(caller_checkpoint_sha256)!=anchor: raise ValueError('caller-held external anchor mismatch')
    cp=b._parse(checkpoint,LIMIT)
    if (_hex(observed_ack_sha256)!=cp['local_ack_sha256'] or
            _pins(observed_local_journal_pins,6)!=p['local_journal_pins'] or
            _pins(observed_peer_pins,4)!=c['candidate_pins'] or
            boot_sample!=p['request']['boot']):
        raise ValueError('ACK/pins/current boot differ from anchored context')
    return dict(state='anchored-bytes-consistent-no-resume',logical_links_verified=True,
                caller_anchor_matched=True,observed_ack_bytes_match=True,
                external_anchor_provenance_verified=False,external_anchor_durability_verified=False,
                historical_completion_proven=False,writer_recovered=False,**flags())
