#!/usr/bin/env python3
"""Client signatures/scopes/replay in local HOST fixtures; no network or device."""
import base64
import json
from pathlib import Path
import tempfile
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import bootstrap_receipt as b
import bootstrap_witness_reference as w
import witness_client_policy as p


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except (ValueError,w.Frozen,OSError): pass
    else: raise AssertionError('unauthenticated/out-of-scope/replayed witness request accepted')


witness_key=Ed25519PrivateKey.generate();client_key=Ed25519PrivateKey.generate()
witness_public=w.public_bytes(witness_key);client_public=w.public_bytes(client_key)
scope=p.create_scope(client_public,witness_public,'1'*64,'2'*64,'3'*64,['publish','observe'])
observe_scope=p.create_scope(client_public,witness_public,'1'*64,'2'*64,'3'*64,['observe'])
request=w.create_request('1'*64,'2'*64,'3'*64,'4'*32)
fresh=w.create_request('1'*64,'2'*64,'3'*64,'5'*32)


def safe(result):
    assert result['client_signature_verified'] and result['witness_response_signature_verified']
    assert result['fixture_scope_and_session_matched']
    for field in (*w.flags(),'policy_source_verified','production_freshness_verified',
                  'witness_deployment_independence_verified','witness_rollback_protection_verified',
                  'witness_non_equivocation_verified','original_response_delivery_verified','writer_recovered'):
        assert result[field] is False
    assert 'checkpoint' not in result
    return result


def signed_change(envelope,field,value,key=client_key,domain=b'SUBMISSION'):
    payload=json.loads(envelope)['payload'];payload[field]=value
    return p._sign(key,domain,b.canonical(payload))


with tempfile.TemporaryDirectory(prefix='q3-witness-policy-',dir='/tmp/opencode') as temporary:
    root=Path(temporary)

    def service(name):
        parent=root/name;parent.mkdir(mode=0o700);info=parent.stat()
        return w.FixtureWitness.create(parent,(info.st_dev,info.st_ino),witness_key)

    def gate(name,active_scope=scope,**kwargs):
        return p.FixtureClientGate(service(name),client_public,active_scope,**kwargs)

    def submission(g,active_request=request,action='publish',active_scope=scope):
        return p.sign_submission(client_key,active_scope,g.challenge(),witness_public,action,active_request)

    def verify(g,response,envelope,active_scope=scope):
        return safe(p.verify_response(response,envelope,active_scope,g.challenge(),client_public,witness_public))

    g=gate('success');challenge=g.challenge()
    assert p.verify_challenge(challenge,scope,client_public,witness_public)
    envelope=submission(g);response=g.handle(envelope);verify(g,response,envelope)
    denied(p._unseal,challenge,witness_public,b'RESPONSE')
    denied(p._unseal,envelope,client_public,b'CHALLENGE')
    observed_submission=submission(g,fresh,'observe');observed_response=g.handle(observed_submission)
    verify(g,observed_response,observed_submission)
    assert g.service.db.execute('SELECT count(*) FROM bindings').fetchone()==(1,)
    denied(p.verify_response,response,observed_submission,scope,challenge,client_public,witness_public)
    changed=signed_change(response,'submission_sha256','0'*64,witness_key,b'RESPONSE')
    denied(p.verify_response,changed,envelope,scope,challenge,client_public,witness_public)
    inner_lookup=g.service.lookup(w.create_request('1'*64,'2'*64,'3'*64,'6'*32))
    changed=signed_change(response,'statement_ascii',inner_lookup.decode(),witness_key,b'RESPONSE')
    denied(p.verify_response,changed,envelope,scope,challenge,client_public,witness_public)
    # A duplicate signed request is rejected BEFORE database work, even if its
    # binding is idempotent at the lower-level fixture witness.
    traces=[];g.service.db.set_trace_callback(traces.append)
    denied(g.handle,envelope)
    assert not traces and g.poisoned and g.service.poisoned
    with mock.patch.object(w.os,'stat',side_effect=AssertionError('read after freeze')):
        denied(g.handle,observed_submission);denied(g.challenge);denied(g.service.lookup,request)
    g.close()

    # Valid CLIENT signatures cannot expand the pinned service-side scope/session.
    for kind in ('foreign-key','action','pending','checkpoint','context','scope','session','challenge','client-id','extra'):
        g=gate('reject-'+kind,observe_scope if kind=='action' else scope)
        active_scope=observe_scope if kind=='action' else scope
        envelope=submission(g,request,'observe' if kind=='action' else 'publish',active_scope)
        if kind=='foreign-key': envelope=p._sign(Ed25519PrivateKey.generate(),b'SUBMISSION',b.canonical(json.loads(envelope)['payload']))
        elif kind=='action': envelope=signed_change(envelope,'action','publish')
        elif kind in ('pending','checkpoint','context'):
            raw=w._request(request);raw[kind+'_sha256']='7'*64
            envelope=signed_change(envelope,'request',raw)
        else:
            field={'scope':'scope_sha256','session':'session_nonce','challenge':'challenge_sha256',
                   'client-id':'client_key_sha256','extra':'extra'}[kind]
            envelope=signed_change(envelope,field,'8'*32 if kind=='session' else '8'*64)
        traces=[];g.service.db.set_trace_callback(traces.append)
        denied(g.handle,envelope)
        assert g.poisoned and g.service.poisoned and not traces and not g.seen
        g.close()

    # Client helper also refuses role/key aliases and non-whitelisted digests.
    denied(p.create_scope,client_public,client_public,'1'*64,'2'*64,'3'*64,['publish'])
    for actions in ([],['publish','publish'],['shell'],['observe',True]):
        denied(p.create_scope,client_public,witness_public,'1'*64,'2'*64,'3'*64,actions)
    denied(p.FixtureClientGate,object(),client_public,scope)
    for field,value in (('schema',True),('admission_enabled',True),('client_key_sha256','0'*64)):
        raw=json.loads(scope);raw[field]=value
        raw_service=service('bad-initial-scope-'+field)
        denied(p.FixtureClientGate,raw_service,client_public,b.canonical(raw))
        assert raw_service.poisoned;raw_service.close()
    g=gate('client-helper')
    denied(p.sign_submission,Ed25519PrivateKey.generate(),scope,g.challenge(),witness_public,'publish',request)
    denied(p.sign_submission,client_key,scope,g.challenge(),witness_public,'execute',request)
    denied(p.sign_submission,client_key,scope,g.challenge(),witness_public,'publish',w.create_request('1'*64,'9'*64,'3'*64,'4'*32))
    denied(p.verify_challenge,g.challenge(),scope,client_public,w.public_bytes(Ed25519PrivateKey.generate()))
    challenge_nonce=p.verify_challenge(g.challenge(),scope,client_public,witness_public)
    denied(submission,g,w.create_request('1'*64,'2'*64,'3'*64,challenge_nonce))
    g.close()

    # A prior signed session cannot authorize another fresh session, even with
    # the same keys/scope/binding. This is not durable anti-rollback protection.
    old=gate('old-session',session_nonce='a'*32);old_submission=submission(old);old_challenge=old.challenge();old.close()
    new=gate('new-session',session_nonce='b'*32)
    assert new.challenge()!=old_challenge
    denied(new.handle,old_submission);assert new.poisoned;new.close()
    # Deliberately reusing the test-only session nonce recreates a challenge.
    # This demonstrates why provisioning/entropy/rollback assumptions remain open.
    reused=gate('reused-test-session',session_nonce='a'*32)
    assert reused.challenge()==old_challenge
    safe(p.verify_response(reused.handle(old_submission),old_submission,scope,old_challenge,client_public,witness_public))
    reused.close()

    # A publish/observe pair cannot reuse the SAME client nonce within a session.
    g=gate('nonce-across-actions');g.handle(submission(g))
    denied(g.handle,submission(g,request,'observe'));assert g.poisoned;g.close()
    g=gate('capacity');g.handle(submission(g))
    with mock.patch.object(p,'MAX_SUBMISSIONS',1): denied(g.handle,submission(g,fresh,'observe'))
    assert g.poisoned;g.close()

    # Signed responses are bound to submission+challenge, not just the inner
    # legacy witness statement. Invalid outer signatures/canonical bytes fail.
    g=gate('response-checks');envelope=submission(g);response=g.handle(envelope)
    for bad in (response+b'\n',response.replace(b'"schema":1',b'"schema":1,"schema":1',1),b'x'*p.LIMIT):
        denied(p.verify_response,bad,envelope,scope,g.challenge(),client_public,witness_public)
    altered=json.loads(response);raw=bytearray(base64.b64decode(altered['signature_b64']));raw[0]^=1
    altered['signature_b64']=base64.b64encode(raw).decode()
    denied(p.verify_response,b.canonical(altered),envelope,scope,g.challenge(),client_public,witness_public)
    g.close()

    # Failure after witness COMMIT does not trigger automatic lookup/retry and
    # cannot recover an original scoped response from a later observation.
    for point in ('after-witness-result','before-response-return'):
        def fault(stage):
            if stage==point: raise OSError('injected response loss')
        g=gate('lost-'+point,fault=fault);parent=g.service.parent_path;parent_pins=g.service.parent_pins;store_pins=g.service.pins
        challenge=g.challenge();envelope=submission(g);denied(g.handle,envelope)
        assert g.poisoned and g.service.poisoned and len(g.seen)==1
        denied(g.handle,envelope);g.close()
        observer=w.FixtureWitness.open_observer(parent,parent_pins,store_pins,witness_key)
        observed_gate=p.FixtureClientGate(observer,client_public,observe_scope)
        observed_envelope=submission(observed_gate,fresh,'observe',observe_scope)
        observed_response=observed_gate.handle(observed_envelope)
        verify(observed_gate,observed_response,observed_envelope,observe_scope)
        denied(p.verify_response,observed_response,envelope,scope,challenge,client_public,witness_public)
        observed_gate.close()

source=Path(p.__file__).read_text()
for forbidden in ('import socket','import subprocess','import controller','def resume','def reset',
                  'def reopen_writer','os.system','os.exec'):
    assert forbidden not in source
print('PASS witness client policy: distinct prior keys, exact scope/actions, signed session/submission/response, nonce claims before delegation, frozen rejects/lost response; no deployment/global replay protection/device admission')
