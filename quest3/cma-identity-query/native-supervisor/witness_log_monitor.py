#!/usr/bin/env python3
"""Bounded HOST model of a signed Merkle log and independent monitor.

Supplied complete prefixes only; no disk/network, service deployment or durable
monitor state. The caller must retain the actual latest monitor anchor outside
the examined tail. Stateless fixture signing cannot establish that provenance.
"""
import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import bootstrap_receipt as b
import bootstrap_witness_reference as w

PROFILE='q3-witness-log-monitor-host-v1'
LIMIT=65536
MAX_ENTRIES=128
MAX_LEAF=16384


def flags():
    return dict(**w.flags(),deployment_independence_verified=False,
        monitor_anchor_provenance_verified=False,monitor_anchor_freshness_verified=False,
        operational_append_only_verified=False,witness_rollback_protection_verified=False,
        witness_non_equivocation_verified=False,hidden_forks_excluded=False,
        original_response_delivery_verified=False,writer_recovered=False)


def _hash(role,data):
    return hashlib.sha256(b'ERIS-Q3-WITNESS-LOG-MONITOR-HOST-V1\0'+role+b'\0'+data).hexdigest()


def _record(kind,**fields):
    return b.canonical(dict(schema=1,profile=PROFILE,producer='host-log-monitor-model',
                            kind=kind,**fields,**flags()))


def _sign(key,role,payload):
    signature=key.sign(b'ERIS-Q3-LOG-MONITOR-SIGNATURE-V1\0'+role+b'\0'+payload)
    return b.canonical(dict(payload=b._parse(payload,LIMIT),signature_b64=base64.b64encode(signature).decode()))


def _unseal(raw,public,role):
    w._key_id(public);value=b._parse(raw,LIMIT)
    try:
        payload=b.canonical(value['payload']);b._parse(payload,LIMIT)
        signature=base64.b64decode(value['signature_b64'],validate=True)
    except (KeyError,TypeError) as error: raise ValueError('log/monitor envelope shape mismatch') from error
    if (len(signature)!=64 or b.canonical(dict(payload=b._parse(payload,LIMIT),
            signature_b64=base64.b64encode(signature).decode()))!=raw):
        raise ValueError('log/monitor envelope canonical mismatch')
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature,
            b'ERIS-Q3-LOG-MONITOR-SIGNATURE-V1\0'+role+b'\0'+payload)
    except InvalidSignature as error: raise ValueError('log/monitor signature mismatch') from error
    return payload


def create_config(witness_public,log_public,monitor_public):
    keys=[w._key_id(key) for key in (witness_public,log_public,monitor_public)]
    if len(set(keys))!=3: raise ValueError('witness/log/monitor key roles must be distinct')
    return _record('config',witness_key_sha256=keys[0],log_key_sha256=keys[1],monitor_key_sha256=keys[2])


def create_entry(witness_public,request,statement):
    envelope=b._parse(statement,w.LIMIT)
    try: observation=envelope['payload']['observation']
    except (KeyError,TypeError) as error: raise ValueError('missing witness observation') from error
    w.verify_statement(statement,request,witness_public,expected_observation=observation)
    return _record('entry',witness_key_sha256=w._key_id(witness_public),
                   request_ascii=request.decode('ascii'),statement_ascii=statement.decode('ascii'))


def _entry(raw,witness_public):
    value=b._parse(raw,MAX_LEAF)
    try:
        request=value['request_ascii'].encode('ascii');statement=value['statement_ascii'].encode('ascii')
        expected=create_entry(witness_public,request,statement)
    except (KeyError,TypeError,AttributeError,UnicodeError) as error: raise ValueError('log entry shape mismatch') from error
    if expected!=raw: raise ValueError('log entry fields/profile mismatch')
    r=w._request(request)
    return r['pending_sha256'],w._hash(b'BINDING',w._binding(request,w._key_id(witness_public)))


def _entries(entries):
    if (not isinstance(entries,(list,tuple)) or len(entries)>MAX_ENTRIES or
            any(not isinstance(leaf,bytes) or not 0<len(leaf)<MAX_LEAF for leaf in entries)):
        raise ValueError('bounded supplied complete prefix required')


def merkle_root(entries):
    """RFC6962-style domain-separated tree shape, NOT an RFC wire protocol."""
    _entries(entries)
    def tree(leaves):
        if not leaves: return hashlib.sha256(b'').digest()
        if len(leaves)==1: return hashlib.sha256(b'\x00'+leaves[0]).digest()
        split=1<<((len(leaves)-1).bit_length()-1)
        return hashlib.sha256(b'\x01'+tree(leaves[:split])+tree(leaves[split:])).digest()
    return tree(entries).hex()


def _head_payload(config,size,root):
    if type(size) is not int or not 0<=size<=MAX_ENTRIES: raise ValueError('invalid log size/type')
    return _record('log-head',config_sha256=_hash(b'CONFIG',config),tree_size=size,root_sha256=w._hex(root))


def sign_fixture_log_head(log_key,witness_public,monitor_public,entries):
    """Sign a supplied prefix root. The untrusted log need NOT validate leaves."""
    _entries(entries)
    config=create_config(witness_public,w.public_bytes(log_key),monitor_public)
    return _sign(log_key,b'LOG-HEAD',_head_payload(config,len(entries),merkle_root(entries)))


def _head(raw,witness_public,log_public,monitor_public):
    config=create_config(witness_public,log_public,monitor_public)
    payload=_unseal(raw,log_public,b'LOG-HEAD');value=b._parse(payload,LIMIT)
    try: expected=_head_payload(config,value['tree_size'],value['root_sha256'])
    except KeyError as error: raise ValueError('missing log-head fields') from error
    if expected!=payload: raise ValueError('foreign log-head config/fields')
    return value


def _scan(entries,witness_public):
    bindings={}
    for leaf in entries:
        pending,binding=_entry(leaf,witness_public)
        if pending in bindings and bindings[pending]!=binding:
            raise ValueError('conflicting witness bindings in supplied log prefix')
        bindings[pending]=binding
    commitment=_hash(b'BINDING-MAP',b.canonical(bindings))
    return len(bindings),commitment


def _checkpoint_payload(config,head,count,scan_hash,predecessor):
    if type(count) is not int or not 0<=count<=MAX_ENTRIES: raise ValueError('invalid binding count')
    if predecessor is not None: w._hex(predecessor)
    return _record('monitor-checkpoint',config_sha256=_hash(b'CONFIG',config),
        log_head_ascii=head.decode('ascii'),distinct_bindings=count,binding_map_sha256=w._hex(scan_hash),
        predecessor_checkpoint_sha256=predecessor)


def checkpoint_commitment(raw):
    # Digest only: never promotes a visible tail to a trusted/latest anchor.
    b._parse(raw,LIMIT)
    return _hash(b'MONITOR-CHECKPOINT',raw)


def _checkpoint(raw,witness_public,log_public,monitor_public):
    config=create_config(witness_public,log_public,monitor_public)
    payload=_unseal(raw,monitor_public,b'MONITOR-CHECKPOINT');value=b._parse(payload,LIMIT)
    try:
        head=value['log_head_ascii'].encode('ascii');h=_head(head,witness_public,log_public,monitor_public)
        expected=_checkpoint_payload(config,head,value['distinct_bindings'],value['binding_map_sha256'],
                                     value['predecessor_checkpoint_sha256'])
    except (KeyError,TypeError,AttributeError,UnicodeError) as error: raise ValueError('monitor checkpoint shape mismatch') from error
    if expected!=payload: raise ValueError('monitor checkpoint fields/profile mismatch')
    if h['tree_size']==0:
        if (h['root_sha256']!=merkle_root([]) or value['predecessor_checkpoint_sha256'] is not None or
                (value['distinct_bindings'],value['binding_map_sha256'])!=_scan([],witness_public)):
            raise ValueError('invalid empty genesis checkpoint')
    elif value['predecessor_checkpoint_sha256'] is None or not 1<=value['distinct_bindings']<=h['tree_size']:
        raise ValueError('non-genesis checkpoint lacks predecessor/bindings')
    return value,h


def create_fixture_genesis(monitor_key,witness_public,log_public,empty_log_head):
    monitor_public=w.public_bytes(monitor_key)
    config=create_config(witness_public,log_public,monitor_public)
    h=_head(empty_log_head,witness_public,log_public,monitor_public)
    if h['tree_size']!=0 or h['root_sha256']!=merkle_root([]): raise ValueError('empty signed head required')
    count,scan=_scan([],witness_public)
    return _sign(monitor_key,b'MONITOR-CHECKPOINT',_checkpoint_payload(config,empty_log_head,count,scan,None))


def prepare_monitor_extension(witness_public,log_public,monitor_public,prior_checkpoint,
                              held_checkpoint_sha256,new_log_head,complete_entries):
    """Validate an extension and return UNSIGNED payload, without state/I/O.

    No automatic lookup, durability, state update or newest-anchor selection.
    The full bounded prefix is required to verify BOTH append-only structure and
    absence of conflicting bindings within the presented prefix.
    """
    config=create_config(witness_public,log_public,monitor_public)
    old,old_head=_checkpoint(prior_checkpoint,witness_public,log_public,monitor_public)
    if w._hex(held_checkpoint_sha256)!=checkpoint_commitment(prior_checkpoint):
        raise ValueError('caller-held monitor anchor mismatch')
    new=_head(new_log_head,witness_public,log_public,monitor_public)
    _entries(complete_entries)
    if not old_head['tree_size']<new['tree_size']==len(complete_entries):
        raise ValueError('strict growth and exact complete prefix required')
    prefix=complete_entries[:old_head['tree_size']]
    if (merkle_root(prefix)!=old_head['root_sha256'] or
            _scan(prefix,witness_public)!=(old['distinct_bindings'],old['binding_map_sha256'])):
        raise ValueError('prior prefix was rewritten/reordered or scan state changed')
    if merkle_root(complete_entries)!=new['root_sha256']: raise ValueError('new prefix/root mismatch')
    count,scan=_scan(complete_entries,witness_public)
    return _checkpoint_payload(config,new_log_head,count,scan,held_checkpoint_sha256)


def advance_fixture_monitor(monitor_key,witness_public,log_public,prior_checkpoint,
                            held_checkpoint_sha256,new_log_head,complete_entries):
    """Stateless fixture signer; does NOT provide the durable-store barrier."""
    payload=prepare_monitor_extension(witness_public,log_public,w.public_bytes(monitor_key),
        prior_checkpoint,held_checkpoint_sha256,new_log_head,complete_entries)
    return _sign(monitor_key,b'MONITOR-CHECKPOINT',payload)


def review_checkpoint(checkpoint,witness_public,log_public,monitor_public,held_checkpoint_sha256):
    value,head=_checkpoint(checkpoint,witness_public,log_public,monitor_public)
    if w._hex(held_checkpoint_sha256)!=checkpoint_commitment(checkpoint):
        raise ValueError('caller-held monitor anchor mismatch')
    return dict(state='signed-monitor-bytes-match-no-admission',log_signature_verified=True,
        monitor_signature_verified=True,caller_anchor_matched=True,tree_size=head['tree_size'],
        distinct_bindings=value['distinct_bindings'],full_prefix_rechecked_here=False,**flags())
