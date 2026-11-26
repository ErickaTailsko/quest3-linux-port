#!/usr/bin/env python3
"""Signed Merkle prefixes/independent monitor in HOST fixtures; no deployment."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import bootstrap_receipt as b
import bootstrap_witness_reference as w
import witness_log_monitor as m


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except ValueError: pass
    else: raise AssertionError('invalid log/monitor prefix or anchor accepted')


def safe(result):
    for field,value in m.flags().items(): assert result[field] is value is False
    assert result['log_signature_verified'] and result['monitor_signature_verified']
    assert result['caller_anchor_matched'] and not result['full_prefix_rechecked_here']
    assert not any(field in result for field in ('next_checkpoint','imported_pins'))
    return result


witness_key=Ed25519PrivateKey.generate();log_key=Ed25519PrivateKey.generate();monitor_key=Ed25519PrivateKey.generate()
wp=w.public_bytes(witness_key);lp=w.public_bytes(log_key);mp=w.public_bytes(monitor_key)
request_a=w.create_request('1'*64,'2'*64,'3'*64,'4'*32)
request_b=w.create_request('5'*64,'6'*64,'7'*64,'8'*32)
request_fork=w.create_request('1'*64,'9'*64,'3'*64,'a'*32)
observed_request_a=w.create_request('1'*64,'2'*64,'3'*64,'b'*32)


def head(entries,key=log_key): return m.sign_fixture_log_head(key,wp,mp,entries)


def advance(old,entries,anchor=None,new_head=None):
    return m.advance_fixture_monitor(monitor_key,wp,lp,old,
        m.checkpoint_commitment(old) if anchor is None else anchor,
        head(entries) if new_head is None else new_head,entries)


def review(checkpoint,anchor=None):
    return safe(m.review_checkpoint(checkpoint,wp,lp,mp,
        m.checkpoint_commitment(checkpoint) if anchor is None else anchor))


assert m.merkle_root([])==hashlib.sha256(b'').hexdigest()
h=lambda data:hashlib.sha256(data).digest()
ha,hb,hc=(h(b'\x00'+leaf) for leaf in (b'a',b'b',b'c'))
assert m.merkle_root([b'a'])==ha.hex()
assert m.merkle_root([b'a',b'b'])==h(b'\x01'+ha+hb).hex()
assert m.merkle_root([b'a',b'b',b'c'])==h(b'\x01'+h(b'\x01'+ha+hb)+hc).hex()
assert m.merkle_root([b'a',b'b'])!=m.merkle_root([b'ab'])

with tempfile.TemporaryDirectory(prefix='q3-log-monitor-',dir='/tmp/opencode') as temporary:
    root=Path(temporary)

    def entry(name,request,key=witness_key):
        parent=root/name;parent.mkdir(mode=0o700);info=parent.stat()
        service=w.FixtureWitness.create(parent,(info.st_dev,info.st_ino),key)
        try: statement=service.publish(request)
        finally: service.close()
        return m.create_entry(w.public_bytes(key),request,statement)

    a=entry('a',request_a);c=entry('fork',request_fork);second=entry('b',request_b)
    parent=root/'a';info=parent.stat();store=parent/w.NAME
    pins=tuple(v for path in (store,store/'lease.lock',store/'witness.sqlite3') for v in (path.stat().st_dev,path.stat().st_ino))
    observer=w.FixtureWitness.open_observer(parent,(info.st_dev,info.st_ino),pins,witness_key)
    observed_statement=observer.lookup(observed_request_a);observer.close()
    observed=m.create_entry(wp,observed_request_a,observed_statement)
    empty_head=head([])
    genesis=m.create_fixture_genesis(monitor_key,wp,lp,empty_head)
    assert review(genesis)['tree_size']==0
    one=advance(genesis,[a]);two=advance(one,[a,second]);three=advance(two,[a,second,observed])
    assert review(one)['distinct_bindings']==1
    assert review(two)['tree_size']==2 and review(two)['distinct_bindings']==2
    assert review(three)['tree_size']==3 and review(three)['distinct_bindings']==2
    prior,json_head=m._checkpoint(three,wp,lp,mp)
    assert prior['predecessor_checkpoint_sha256']==m.checkpoint_commitment(two)
    assert json_head['root_sha256']==m.merkle_root([a,second,observed])

    # Strict growth, exact full-prefix availability and preserved prior entries.
    denied(advance,two,[a])
    denied(advance,two,[a,second])
    denied(advance,two,[c,second])
    denied(advance,two,[second,a,observed])
    denied(advance,two,[c,second,observed])
    denied(advance,two,[observed,a,second])
    denied(advance,two,[observed],new_head=head([a,second,observed]))
    denied(advance,two,[a,second,observed],new_head=head([a,second,c]))
    denied(advance,one,[a,second],anchor=m.checkpoint_commitment(two))
    denied(review,one,m.checkpoint_commitment(two))

    # Append-only hashes alone do not enforce semantic binding uniqueness.
    # These new roots are valid extensions, but monitor scans reject their leaves.
    denied(advance,two,[a,second,c])
    denied(advance,two,[a,second,b'not a canonical witness entry'])
    foreign=entry('foreign-witness',request_b,Ed25519PrivateKey.generate())
    denied(advance,two,[a,second,foreign])
    denied(advance,two,[a,second,observed],new_head=head([a,second,observed],Ed25519PrivateKey.generate()))
    denied(m.create_config,wp,wp,mp)
    denied(m.create_config,wp,lp,lp)
    denied(m.create_fixture_genesis,monitor_key,wp,lp,head([a]))

    # Signed but structurally malformed headers/checkpoints still fail closed.
    for field,value in (('tree_size',True),('tree_size',129),('config_sha256','0'*64),
                        ('root_sha256','0'*64),('admission_enabled',True)):
        payload=json.loads(head([a]))['payload'];payload[field]=value
        bad_head=m._sign(log_key,b'LOG-HEAD',b.canonical(payload))
        denied(advance,genesis,[a],new_head=bad_head)
    for field,value in (('distinct_bindings',True),('distinct_bindings',0),
                        ('predecessor_checkpoint_sha256',None),('config_sha256','0'*64),
                        ('admission_enabled',True)):
        payload=json.loads(one)['payload'];payload[field]=value
        bad_checkpoint=m._sign(monitor_key,b'MONITOR-CHECKPOINT',b.canonical(payload))
        denied(review,bad_checkpoint)
    payload=json.loads(one)['payload'];payload['binding_map_sha256']='0'*64
    bad_scan=m._sign(monitor_key,b'MONITOR-CHECKPOINT',b.canonical(payload))
    # Signature-only inspection cannot recompute a scan, but a full extension does.
    assert not review(bad_scan)['full_prefix_rechecked_here']
    denied(advance,bad_scan,[a,second])
    envelope=json.loads(three);signature=bytearray(base64.b64decode(envelope['signature_b64']));signature[0]^=1
    envelope['signature_b64']=base64.b64encode(signature).decode()
    denied(review,b.canonical(envelope))
    denied(review,three+b'\n')
    denied(review,three.replace(b'"schema":1',b'"schema":1,"schema":1',1))
    denied(m._unseal,empty_head,lp,b'MONITOR-CHECKPOINT')
    for entries in (None,[a]*(m.MAX_ENTRIES+1),[b'x'*m.MAX_LEAF],[b''],['not bytes']):
        denied(head,entries)

    # The model cannot ensure that its input anchor is the latest durable one.
    # A stale genesis permits the same monitor key to endorse another branch.
    alternate_one=advance(genesis,[c])
    assert review(alternate_one)['tree_size']==1
    assert m._checkpoint(alternate_one,wp,lp,mp)[1]['root_sha256']!=m._checkpoint(one,wp,lp,mp)[1]['root_sha256']
    assert not review(alternate_one)['monitor_anchor_freshness_verified']
    denied(advance,genesis,[c],anchor=m.checkpoint_commitment(one))
    denied(advance,one,[c,second])
    # Hiding alternate_one still leaves a coherent presented extension of one.
    assert not review(two)['hidden_forks_excluded']

source=Path(m.__file__).read_text()
for forbidden in ('import os','import socket','import subprocess','open(', 'exec(', 'eval(', 'import controller'):
    assert forbidden not in source
print('PASS witness log/monitor: distinct keys, signed Merkle heads, bounded full-prefix extension, binding scan, rollback/rewrite/conflict rejection and stale-anchor/hidden-fork limits; no I/O/deployment/admission')
