#!/usr/bin/env python3
"""Read-only supplied-byte witness audit. No file/network reads or admission API.

Detects conflicting signed bindings that are actually PRESENTED, not hidden
forks or rollback in general. A caller-held old binding digest is mandatory for
anchored comparison; its independent provenance is not established here.
"""
import hashlib

import bootstrap_receipt as b
import bootstrap_witness_reference as w

PROFILE='q3-witness-audit-host-v1'
MAX_OBSERVATIONS=32
MAX_EVIDENCE=4*w.LIMIT


def flags():
    return dict(**w.flags(),witness_rollback_protection_verified=False,
                witness_non_equivocation_verified=False,hidden_forks_excluded=False,
                deployment_independence_verified=False,anchor_provenance_verified=False,
                freshness_verified=False,
                original_response_delivery_verified=False,historical_bootstrap_execution_proven=False,
                rollback_cause_proven=False,writer_recovered=False,must_remain_frozen=True)


def _verified(prior_key,request,statement):
    # Observation semantics remain distinct: audit verifies what was signed,
    # never upgrades a later lookup into original publication/delivery evidence.
    envelope=b._parse(statement,w.LIMIT)
    try: observation=envelope['payload']['observation']
    except (KeyError,TypeError) as error: raise ValueError('missing witness observation') from error
    checked=w.verify_statement(statement,request,prior_key,expected_observation=observation)
    return w._request(request),checked


def build_conflict_evidence(prior_key,first_request,first_statement,second_request,second_statement):
    """Preserve two valid signatures for distinct bindings of the SAME pending.

    Their existence proves incompatible signed claims under the supplied key;
    it does not identify cause, time, authorization, which branch is correct or
    the physical actor that controlled the key. Different keys/pending IDs are
    not accepted as this form of conflict evidence.
    """
    first,f=_verified(prior_key,first_request,first_statement)
    second,s=_verified(prior_key,second_request,second_statement)
    if (first['pending_sha256']!=second['pending_sha256'] or
            f['binding_sha256']==s['binding_sha256']):
        raise ValueError('two distinct signed bindings for the same pending required')
    records=sorted([
        dict(binding_sha256=f['binding_sha256'],request_ascii=first_request.decode('ascii'),
             statement_ascii=first_statement.decode('ascii')),
        dict(binding_sha256=s['binding_sha256'],request_ascii=second_request.decode('ascii'),
             statement_ascii=second_statement.decode('ascii'))],key=lambda record:record['binding_sha256'])
    return b.canonical(dict(schema=1,profile=PROFILE,producer='host-readonly-audit',
        kind='conflicting-signed-bindings',witness_key_sha256=w._key_id(prior_key),
        pending_sha256=first['pending_sha256'],records=records,**flags()))


def verify_conflict_evidence(evidence,prior_key):
    """Recheck a portable artifact against a caller's PRIOR witness public key."""
    value=b._parse(evidence,MAX_EVIDENCE)
    try:
        records=value['records']
        if not isinstance(records,list) or len(records)!=2: raise ValueError('two records required')
        expected=build_conflict_evidence(prior_key,
            records[0]['request_ascii'].encode('ascii'),records[0]['statement_ascii'].encode('ascii'),
            records[1]['request_ascii'].encode('ascii'),records[1]['statement_ascii'].encode('ascii'))
    except (KeyError,TypeError,AttributeError,UnicodeError) as error:
        raise ValueError('conflict evidence shape/encoding mismatch') from error
    if expected!=evidence: raise ValueError('noncanonical/foreign conflict evidence')
    return dict(state='signed-conflict-detected',signed_conflict_detected=True,
        signed_statements_verified=2,witness_key_sha256=w._key_id(prior_key),
        pending_sha256=value['pending_sha256'],evidence_sha256=hashlib.sha256(
            b'ERIS-Q3-WITNESS-CONFLICT-EVIDENCE-V1\0'+evidence).hexdigest(),**flags())


def audit(prior_key,anchored_request,anchored_statement,held_binding_sha256,observations):
    """Compare supplied statements to a previously held digest, never rebase it.

    No observations -> anchor-only. No presented conflict -> NOT proof of
    non-equivocation. Invalid or foreign input rejects the entire comparison.
    No next-checkpoint, response-recovery or controller capability is returned.
    """
    w._hex(held_binding_sha256)
    baseline,base=_verified(prior_key,anchored_request,anchored_statement)
    if held_binding_sha256!=base['binding_sha256']: raise ValueError('caller-held binding anchor mismatch')
    if not isinstance(observations,(list,tuple)) or len(observations)>MAX_OBSERVATIONS:
        raise ValueError('bounded supplied observation sequence required')
    bindings={held_binding_sha256}; seen={hashlib.sha256(anchored_statement).hexdigest()}
    duplicate_count=0; evidence=None
    for pair in observations:
        if not isinstance(pair,(list,tuple)) or len(pair)!=2: raise ValueError('request/statement pair required')
        request,statement=pair
        value,checked=_verified(prior_key,request,statement)
        if value['pending_sha256']!=baseline['pending_sha256']:
            raise ValueError('foreign pending ID is not an observation of this transaction')
        statement_hash=hashlib.sha256(statement).hexdigest()
        duplicate_count+=int(statement_hash in seen); seen.add(statement_hash)
        bindings.add(checked['binding_sha256'])
        if checked['binding_sha256']!=held_binding_sha256 and evidence is None:
            evidence=build_conflict_evidence(prior_key,anchored_request,anchored_statement,request,statement)
    result=dict(state='signed-conflict-detected' if evidence is not None else
        'anchor-only-no-new-observation' if not observations else 'presented-bindings-match-no-safety-proof',
        caller_anchor_matched=True,presented_signatures_verified=len(observations)+1,
        distinct_presented_bindings=len(bindings),duplicate_statements=duplicate_count,
        signed_conflict_detected=evidence is not None,**flags())
    if evidence is not None:
        checked=verify_conflict_evidence(evidence,prior_key)
        result.update(conflict_evidence_ascii=evidence.decode('ascii'),evidence_sha256=checked['evidence_sha256'])
    return result
