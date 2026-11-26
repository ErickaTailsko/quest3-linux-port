#!/usr/bin/env python3
"""Signed witness forks/anchors in local HOST fixtures only; no peer commands."""
import base64
import json
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import bootstrap_receipt as b
import bootstrap_witness_reference as w
import witness_audit as a


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except ValueError: pass
    else: raise AssertionError('invalid signed-conflict/anchor claim accepted')


def safe(result):
    for key,value in a.flags().items(): assert result[key] is value
    assert not any(key in result for key in ('checkpoint','next_checkpoint','imported_pins'))
    return result


key=Ed25519PrivateKey.generate();public=w.public_bytes(key)
request=w.create_request('1'*64,'2'*64,'3'*64,'4'*32)
fresh=w.create_request('1'*64,'2'*64,'3'*64,'5'*32)
conflicting=w.create_request('1'*64,'6'*64,'3'*64,'7'*32)
changed_context=w.create_request('1'*64,'2'*64,'8'*64,'9'*32)
foreign_pending=w.create_request('a'*64,'2'*64,'3'*64,'b'*32)

with tempfile.TemporaryDirectory(prefix='q3-witness-audit-',dir='/tmp/opencode') as temporary:
    root=Path(temporary)

    def statement(name,active_request,active_key=key):
        path=root/name;path.mkdir(mode=0o700);info=path.stat()
        service=w.FixtureWitness.create(path,(info.st_dev,info.st_ino),active_key)
        try: return service.publish(active_request)
        finally: service.close()

    original=statement('original',request)
    original_key_id=w._key_id(public)
    binding=w.verify_statement(original,request,public,expected_observation='publication-confirmed')['binding_sha256']
    path=root/'original';info=path.stat();store=path/w.NAME
    pins=tuple(v for item in (store,store/'lease.lock',store/'witness.sqlite3') for v in (item.stat().st_dev,item.stat().st_ino))
    observer=w.FixtureWitness.open_observer(path,(info.st_dev,info.st_ino),pins,key)
    observed=observer.lookup(fresh);observer.close()
    fork=statement('fork',conflicting)
    context_fork=statement('context-fork',changed_context)
    unrelated=statement('unrelated',foreign_pending)

    result=safe(a.audit(public,request,original,binding,[]))
    assert result['state']=='anchor-only-no-new-observation' and not result['signed_conflict_detected']
    result=safe(a.audit(public,request,original,binding,[(fresh,observed),(request,original)]))
    assert result['state']=='presented-bindings-match-no-safety-proof'
    assert result['distinct_presented_bindings']==1 and result['duplicate_statements']==1
    assert not result['hidden_forks_excluded']  # a hidden fork already exists in this fixture

    result=safe(a.audit(public,request,original,binding,[(fresh,observed),(conflicting,fork)]))
    assert result['signed_conflict_detected'] and result['distinct_presented_bindings']==2
    assert result['presented_signatures_verified']==3
    repeated=safe(a.audit(public,request,original,binding,
        [(request,original)]*(a.MAX_OBSERVATIONS-1)+[(conflicting,fork)]))
    assert repeated['signed_conflict_detected']  # duplicate signatures are not independent votes
    evidence=result['conflict_evidence_ascii'].encode('ascii')
    checked=safe(a.verify_conflict_evidence(evidence,public))
    assert checked['signed_statements_verified']==2 and checked['witness_key_sha256']==original_key_id
    assert checked['evidence_sha256']==result['evidence_sha256']
    assert a.build_conflict_evidence(public,conflicting,fork,request,original)==evidence
    observed_conflict=a.build_conflict_evidence(public,fresh,observed,conflicting,fork)
    assert safe(a.verify_conflict_evidence(observed_conflict,public))['signed_conflict_detected']
    assert safe(a.audit(public,request,original,binding,[(changed_context,context_fork)]))['signed_conflict_detected']
    # Witness statements provide no ordering: no later/earlier or rollback cause is inferred.
    alternate_binding=w.verify_statement(fork,conflicting,public,expected_observation='publication-confirmed')['binding_sha256']
    reversed_result=safe(a.audit(public,conflicting,fork,alternate_binding,[(request,original)]))
    assert reversed_result['evidence_sha256']==checked['evidence_sha256']
    assert not reversed_result['rollback_cause_proven']

    denied(a.audit,public,request,original,'0'*64,[(conflicting,fork)])
    denied(a.audit,public,conflicting,fork,binding,[])
    denied(a.audit,public,request,original,None,[])
    denied(a.audit,public,request,original,binding,[(foreign_pending,unrelated)])
    denied(a.audit,public,request,original,binding,[(request,original)]*(a.MAX_OBSERVATIONS+1))
    denied(a.audit,public,request,original,binding,'not pairs')
    denied(a.audit,public,request,original,binding,[(request,)])
    denied(a.audit,public,request,original,binding,[(request,original+b'\n')])
    denied(a.audit,public,request,original,binding,[(fresh,original)])
    denied(a.audit,public,request,original,binding,[(conflicting,fork),(fresh,b'bad')])
    denied(a.build_conflict_evidence,public,request,original,fresh,observed)
    denied(a.build_conflict_evidence,public,request,original,foreign_pending,unrelated)
    other_key=Ed25519PrivateKey.generate()
    foreign_signature=statement('foreign-key',conflicting,other_key)
    denied(a.build_conflict_evidence,public,request,original,conflicting,foreign_signature)
    denied(a.verify_conflict_evidence,evidence,w.public_bytes(other_key))

    for field,replacement in (('schema',True),('must_remain_frozen',False),('admission_enabled',True),
                               ('pending_sha256','0'*64),('witness_key_sha256','0'*64),('unknown',True)):
        changed=json.loads(evidence);changed[field]=replacement
        denied(a.verify_conflict_evidence,b.canonical(changed),public)
    changed=json.loads(evidence);changed['records'].reverse()
    denied(a.verify_conflict_evidence,b.canonical(changed),public)  # frozen canonical sort
    changed=json.loads(evidence);changed['records'][0]['binding_sha256']='0'*64
    denied(a.verify_conflict_evidence,b.canonical(changed),public)
    changed=json.loads(evidence)
    inner=json.loads(changed['records'][0]['statement_ascii'])
    signature=bytearray(base64.b64decode(inner['signature_b64']));signature[0]^=1
    inner['signature_b64']=base64.b64encode(signature).decode()
    changed['records'][0]['statement_ascii']=b.canonical(inner).decode()
    denied(a.verify_conflict_evidence,b.canonical(changed),public)
    for bad in (evidence+b'\n',evidence.replace(b'"schema":1',b'"schema":1,"schema":1',1),b'x'*a.MAX_EVIDENCE):
        denied(a.verify_conflict_evidence,bad,public)

    # Selecting the fork itself as a new baseline hides the prior conflict from
    # this input subset. The API cannot authenticate the caller's anchor source.
    self_selected=safe(a.audit(public,conflicting,fork,alternate_binding,[]))
    assert not self_selected['anchor_provenance_verified']
    assert not self_selected['hidden_forks_excluded'] and self_selected['must_remain_frozen']

source=Path(a.__file__).read_text()
for forbidden in ('import os','import socket','import subprocess','open(', 'exec(', 'eval(', 'import controller'):
    assert forbidden not in source
print('PASS witness audit: prior binding anchor, presented signed forks, portable two-signature evidence, invalid/foreign input rejection and hidden-fork/self-selected-anchor limits; no I/O/admission/resume')
