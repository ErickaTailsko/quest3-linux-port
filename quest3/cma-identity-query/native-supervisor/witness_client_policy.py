#!/usr/bin/env python3
"""Authenticated client-policy wrapper for HOST witness fixtures only.

No socket, account/service setup, operational keys or controller integration.
An injected scope is a prior trust assumption, not authenticated policy origin.
Raw FixtureWitness remains a low-level test API, NOT an authenticated endpoint.
"""
import base64
import hashlib
import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import bootstrap_receipt as b
import bootstrap_witness_reference as w

PROFILE='q3-witness-client-policy-host-v1'
LIMIT=65536
MAX_SUBMISSIONS=32


def _hash(role,data):
    return hashlib.sha256(b'ERIS-Q3-WITNESS-CLIENT-POLICY-HOST-V1\0'+role+b'\0'+data).hexdigest()


def _record(kind,**fields):
    return b.canonical(dict(schema=1,profile=PROFILE,producer='host-fixture-client-policy',
                            kind=kind,**fields,**w.flags()))


def _sign(key,domain,payload):
    return b.canonical(dict(payload=b._parse(payload,LIMIT),signature_b64=base64.b64encode(
        key.sign(b'ERIS-Q3-WITNESS-CLIENT-POLICY-SIGNATURE-V1\0'+domain+b'\0'+payload)).decode('ascii')))


def _unseal(raw,public,domain):
    w._key_id(public)
    value=b._parse(raw,LIMIT)
    try:
        payload=b.canonical(value['payload']);b._parse(payload,LIMIT)
        signature=base64.b64decode(value['signature_b64'],validate=True)
    except (KeyError,TypeError) as error: raise ValueError('client-policy signed envelope mismatch') from error
    if (len(signature)!=64 or b.canonical(dict(payload=b._parse(payload,LIMIT),
            signature_b64=base64.b64encode(signature).decode('ascii')))!=raw):
        raise ValueError('noncanonical client-policy envelope')
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature,
            b'ERIS-Q3-WITNESS-CLIENT-POLICY-SIGNATURE-V1\0'+domain+b'\0'+payload)
    except InvalidSignature as error: raise ValueError('client-policy signature mismatch') from error
    return payload


def create_scope(client_public,witness_public,pending_sha256,checkpoint_sha256,context_sha256,actions):
    client=w._key_id(client_public);witness=w._key_id(witness_public)
    if client==witness: raise ValueError('client and witness keys must have distinct roles')
    if (not isinstance(actions,(list,tuple)) or not actions or
            any(type(action) is not str or action not in ('observe','publish') for action in actions) or
            len(set(actions))!=len(actions)):
        raise ValueError('explicit distinct witness actions required')
    return _record('scope',client_key_sha256=client,witness_key_sha256=witness,
        pending_sha256=w._hex(pending_sha256),checkpoint_sha256=w._hex(checkpoint_sha256),
        context_sha256=w._hex(context_sha256),actions=sorted(actions))


def _scope(raw,client_public,witness_public):
    value=b._parse(raw,LIMIT)
    try:
        expected=create_scope(client_public,witness_public,value['pending_sha256'],
            value['checkpoint_sha256'],value['context_sha256'],value['actions'])
    except KeyError as error: raise ValueError('missing client scope fields') from error
    if expected!=raw: raise ValueError('scope identity/canonical fields mismatch')
    return value


def _challenge(scope,session_nonce):
    return _record('challenge',scope_sha256=_hash(b'SCOPE',scope),session_nonce=w._hex(session_nonce,32))


def verify_challenge(signed_challenge,scope,client_public,witness_public):
    _scope(scope,client_public,witness_public)
    payload=_unseal(signed_challenge,witness_public,b'CHALLENGE')
    value=b._parse(payload,LIMIT)
    try: expected=_challenge(scope,value['session_nonce'])
    except KeyError as error: raise ValueError('missing challenge nonce') from error
    if expected!=payload: raise ValueError('challenge scope/profile mismatch')
    return value['session_nonce']  # Context only, NOT proof of production freshness.


def _submission(scope,signed_challenge,action,request,client_public,witness_public):
    approved=_scope(scope,client_public,witness_public)
    nonce=verify_challenge(signed_challenge,scope,client_public,witness_public)
    r=w._request(request)
    if (action not in approved['actions'] or type(action) is not str or
            any(r[key]!=approved[key] for key in ('pending_sha256','checkpoint_sha256','context_sha256')) or
            r['nonce']==nonce):
        raise ValueError('request outside prior scope or nonce roles alias')
    return _record('submission',scope_sha256=_hash(b'SCOPE',scope),
        challenge_sha256=_hash(b'CHALLENGE',signed_challenge),session_nonce=nonce,
        action=action,request=r,client_key_sha256=w._key_id(client_public))


def sign_submission(client_key,scope,signed_challenge,witness_public,action,request):
    """Sign only an exact scoped HOST request; never a device command."""
    payload=_submission(scope,signed_challenge,action,request,w.public_bytes(client_key),witness_public)
    return _sign(client_key,b'SUBMISSION',payload)


def _verify_submission(envelope,scope,signed_challenge,client_public,witness_public):
    payload=_unseal(envelope,client_public,b'SUBMISSION')
    value=b._parse(payload,LIMIT)
    try:
        request=b.canonical(value['request']);action=value['action']
        expected=_submission(scope,signed_challenge,action,request,client_public,witness_public)
    except KeyError as error: raise ValueError('missing submission fields') from error
    if expected!=payload: raise ValueError('foreign session/scope/submission')
    return request,action


def _response(envelope,scope,signed_challenge,statement,client_public,witness_public):
    request,action=_verify_submission(envelope,scope,signed_challenge,client_public,witness_public)
    observation='publication-confirmed' if action=='publish' else 'record-observed'
    w.verify_statement(statement,request,witness_public,expected_observation=observation)
    return _record('response',submission_sha256=_hash(b'SUBMISSION',envelope),
        scope_sha256=_hash(b'SCOPE',scope),challenge_sha256=_hash(b'CHALLENGE',signed_challenge),
        client_key_sha256=w._key_id(client_public),witness_key_sha256=w._key_id(witness_public),
        action=action,statement_ascii=statement.decode('ascii'))


def verify_response(response,envelope,scope,signed_challenge,client_public,witness_public):
    payload=_unseal(response,witness_public,b'RESPONSE')
    value=b._parse(payload,LIMIT)
    try:
        expected=_response(envelope,scope,signed_challenge,value['statement_ascii'].encode('ascii'),
                           client_public,witness_public)
    except (KeyError,TypeError,AttributeError,UnicodeError) as error:
        raise ValueError('client-policy response shape mismatch') from error
    if payload!=expected: raise ValueError('response does not bind this exact submission/session')
    return dict(state='scoped-fixture-response-no-admission',client_signature_verified=True,
        witness_response_signature_verified=True,fixture_scope_and_session_matched=True,
        policy_source_verified=False,production_freshness_verified=False,
        witness_deployment_independence_verified=False,witness_rollback_protection_verified=False,
        witness_non_equivocation_verified=False,original_response_delivery_verified=False,
        writer_recovered=False,**w.flags())


class FixtureClientGate:
    """Single-threaded fixture front door; failures freeze gate AND witness handle.

    Nonce claims live only in this handle. A fresh signed session challenge is
    created per gate; this is not a durable client log or rollback protection.
    Keys/scope are injected by the trusted fixture owner, not learnt from peers.
    """

    def __init__(self,service,client_public,scope,*,session_nonce=None,fault=None):
        if not isinstance(service,w.FixtureWitness): raise ValueError('host fixture witness required')
        self.service=service;self.client_public=client_public;self.scope=scope
        self.witness_public=w.public_bytes(service.key)
        self.poisoned=False;self.closed=False;self.seen=set();self.fault=fault
        try:
            _scope(scope,client_public,self.witness_public)
            service._check()
            nonce=secrets.token_hex(16) if session_nonce is None else w._hex(session_nonce,32)
            self.signed_challenge=_sign(service.key,b'CHALLENGE',_challenge(scope,nonce))
        except BaseException:
            self.poisoned=True;service.poisoned=True;raise

    def _alive(self):
        if self.poisoned or self.closed or self.service.poisoned or self.service.root is None:
            raise w.Frozen('closed/frozen client gate or witness')
        if w.public_bytes(self.service.key)!=self.witness_public: raise w.Frozen('witness key changed')

    def challenge(self):
        try:
            self._alive()
            return self.signed_challenge
        except BaseException:
            self.poisoned=True;self.service.poisoned=True;raise

    def close(self):
        self.closed=True;self.service.close()

    def handle(self,envelope):
        try:
            self._alive()
            request,action=_verify_submission(envelope,self.scope,self.signed_challenge,
                                              self.client_public,self.witness_public)
            nonce=w._request(request)['nonce']
            if nonce in self.seen or len(self.seen)>=MAX_SUBMISSIONS:
                raise w.Frozen('duplicate submission nonce or bounded session exhausted')
            self.seen.add(nonce)  # Claim BEFORE any witness database operation.
            statement=self.service.publish(request) if action=='publish' else self.service.lookup(request)
            if self.fault is not None: self.fault('after-witness-result')
            response=_sign(self.service.key,b'RESPONSE',_response(envelope,self.scope,self.signed_challenge,
                                        statement,self.client_public,self.witness_public))
            if self.fault is not None: self.fault('before-response-return')
            self._alive()
            return response
        except BaseException:
            self.poisoned=True;self.service.poisoned=True;raise
