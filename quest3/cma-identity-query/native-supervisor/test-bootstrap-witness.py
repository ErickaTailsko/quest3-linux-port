#!/usr/bin/env python3
"""SQLite/Ed25519 witness in private HOST fixtures; no network/device/service setup."""
import base64
import json
import os
from pathlib import Path
import select
import signal
import socket
import sqlite3
import tempfile
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import bootstrap_witness_reference as w
import bootstrap_receipt as b


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except (w.Frozen,ValueError,OSError,sqlite3.Error): pass
    else: raise AssertionError('invalid witness publication/statement accepted')


key=Ed25519PrivateKey.generate();public=w.public_bytes(key)
request=w.create_request('1'*64,'2'*64,'3'*64,'4'*32)
fresh_request=w.create_request('1'*64,'2'*64,'3'*64,'5'*32)
conflict=w.create_request('1'*64,'6'*64,'3'*64,'7'*32)


def verified(statement,active_request=request,observation='publication-confirmed'):
    result=w.verify_statement(statement,active_request,public,expected_observation=observation)
    assert result['signature_verified'] and result['expected_request_matched']
    for field in (*w.flags(),'witness_deployment_independence_verified','original_response_delivery_verified',
                  'witness_rollback_protection_verified','witness_non_equivocation_verified',
                  'historical_bootstrap_execution_proven','writer_recovered'):
        assert result[field] is False
    assert 'checkpoint' not in result
    return result


with tempfile.TemporaryDirectory(prefix='q3-witness-',dir=os.environ.get('Q3_WITNESS_TEST_TMP','/tmp/opencode')) as temporary:
    root=Path(temporary)

    def fixture(name):
        path=root/name;path.mkdir(mode=0o700);info=path.stat()
        return path,(info.st_dev,info.st_ino)

    path,pins=fixture('success');service=w.FixtureWitness.create(path,pins,key)
    witness_pins=service.pins
    assert service.db.execute('PRAGMA synchronous').fetchone()==(2,)
    assert service.db.execute('PRAGMA journal_mode').fetchone()==('delete',)
    statement=service.publish(request);result=verified(statement)
    assert service.publish(request)==statement  # same digest binding, deterministic signature
    fresh=service.publish(fresh_request);verified(fresh,fresh_request)
    assert service.db.execute('SELECT count(*) FROM bindings').fetchone()==(1,)
    observed=service.lookup(fresh_request);verified(observed,fresh_request,'record-observed')
    denied(verified,observed,fresh_request,'publication-confirmed')
    denied(verified,statement,fresh_request)
    denied(w.verify_statement,statement,request,w.public_bytes(Ed25519PrivateKey.generate()),expected_observation='publication-confirmed')
    for field,replacement in (('observation','record-observed'),('admission_enabled',True),
                               ('request_sha256','0'*64),('schema',True)):
        changed=json.loads(statement);changed['payload'][field]=replacement
        denied(verified,b.canonical(changed))
    changed=json.loads(statement);raw=bytearray(base64.b64decode(changed['signature_b64']));raw[0]^=1
    changed['signature_b64']=base64.b64encode(raw).decode();denied(verified,b.canonical(changed))
    for signature in ('!!',base64.b64encode(b'x'*63).decode()):
        changed=json.loads(statement);changed['signature_b64']=signature;denied(verified,b.canonical(changed))
    denied(verified,statement+b'\n')
    duplicate=statement.replace(b'"schema":1',b'"schema":1,"schema":1',1)
    denied(verified,duplicate)
    denied(w.FixtureWitness.create,path,pins,key)
    denied(w.FixtureWitness.open_observer,path,pins,witness_pins,key)  # live lease held
    denied(service.publish,conflict)
    assert service.poisoned
    # A poisoned handle performs no further file/database reads or signing.
    with mock.patch.object(w.os,'stat',side_effect=AssertionError('read after freeze')):
        denied(service.lookup,request);denied(service.publish,request)
    service.close()
    observer=w.FixtureWitness.open_observer(path,pins,witness_pins,key)
    lookup=observer.lookup(fresh_request);verified(lookup,fresh_request,'record-observed')
    assert lookup==observed  # deterministic observation, not proof of delivery/time
    assert observer.db.execute('PRAGMA query_only').fetchone()==(1,)
    denied(observer.publish,request);assert observer.poisoned;observer.close()
    denied(w.FixtureWitness.open_observer,path,pins,witness_pins,Ed25519PrivateKey.generate())
    denied(w.FixtureWitness.open_observer,path,pins,(*witness_pins[:-1],witness_pins[-1]+1),key)

    # Every uncertain publication freezes; explicit reopen is observation only.
    for stage in ('before-commit','after-commit','directory-fsync','before-sign','before-return'):
        path,pins=fixture('fault-'+stage)
        def fault(point):
            if point==stage: raise OSError('injected '+stage)
        service=w.FixtureWitness.create(path,pins,key,fault=fault);witness_pins=service.pins
        denied(service.publish,request);assert service.poisoned
        denied(service.lookup,request)
        service.close()  # SQLite may roll back its own uncommitted local transaction
        observer=w.FixtureWitness.open_observer(path,pins,witness_pins,key)
        if stage=='before-commit': denied(observer.lookup,fresh_request)
        else:
            later=observer.lookup(fresh_request);verified(later,fresh_request,'record-observed')
            denied(verified,later,fresh_request,'publication-confirmed')
        observer.close();denied(w.FixtureWitness.create,path,pins,key)

    # File/identity replacements and foreign files cannot silently select a new store.
    for target in ('root','lease','database','extra','key-id'):
        path,pins=fixture('replace-'+target);service=w.FixtureWitness.create(path,pins,key)
        service.publish(request);store=path/w.NAME
        if target=='root': store.rename(path/'retained-root');store.mkdir(mode=0o700)
        elif target=='lease':
            (store/'lease.lock').rename(store/'retained-lease')
            fd=os.open(store/'lease.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        elif target=='database':
            (store/'witness.sqlite3').rename(store/'retained-database')
            fd=os.open(store/'witness.sqlite3',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        elif target=='extra': (store/'foreign').write_bytes(b'foreign')
        else: service.db.execute('UPDATE identity SET key_id=?',('0'*64,))
        denied(service.lookup,fresh_request);assert service.poisoned;service.close()

    # Mutation in a host test hook before returning a signature is rejected.
    for stage in ('before-sign','before-return'):
        path,pins=fixture('statement-race-'+stage);service=w.FixtureWitness.create(path,pins,key)
        def corrupt(point):
            if point==stage: service.db.execute('DELETE FROM bindings')
        service.fault=corrupt;denied(service.publish,request)
        assert service.poisoned;service.close()

    path,pins=fixture('absent');service=w.FixtureWitness.create(path,pins,key)
    denied(service.lookup,request);assert service.poisoned;service.close()

    path,pins=fixture('capacity');service=w.FixtureWitness.create(path,pins,key)
    service.publish(request)
    with mock.patch.object(w,'MAX_BINDINGS',1):
        denied(service.publish,w.create_request('8'*64,'2'*64,'3'*64,'9'*32))
    assert service.poisoned;service.close()

    # A signature alone cannot detect a cloned/rolled-back witness store with the
    # same key: two isolated fixture stores can sign conflicting bindings.
    path,pins=fixture('alternate-history');alternate=w.FixtureWitness.create(path,pins,key)
    alternate_statement=alternate.publish(conflict)
    alternate_result=verified(alternate_statement,conflict)
    assert not alternate_result['witness_non_equivocation_verified']
    assert not alternate_result['witness_rollback_protection_verified']
    denied(verified,alternate_statement,request)
    alternate.close()

    # SIGKILL after COMMIT but before response: a new witness-side read can attest
    # what exists, but cannot recreate the original publication/delivery response.
    path,pins=fixture('killed');left,right=socket.socketpair();pid=os.fork()
    if pid==0:
        left.close()
        def pause(point):
            if point=='after-commit': right.sendall(b'R');right.recv(1)
        try:
            service=w.FixtureWitness.create(path,pins,key,fault=pause);service.publish(request);os._exit(3)
        except BaseException: os._exit(4)
    right.close()
    try:
        ready,_,_=select.select([left],[],[],5);assert ready and left.recv(1)==b'R'
        store=path/w.NAME
        witness_pins=tuple(v for p in (store,store/'lease.lock',store/'witness.sqlite3') for v in (p.stat().st_dev,p.stat().st_ino))
    finally:
        os.kill(pid,signal.SIGKILL);os.waitpid(pid,0);left.close()
    observer=w.FixtureWitness.open_observer(path,pins,witness_pins,key)
    later=observer.lookup(fresh_request);verified(later,fresh_request,'record-observed')
    denied(verified,later,fresh_request,'publication-confirmed');observer.close()

source=Path(w.__file__).read_text()
for forbidden in ('import socket','import subprocess','import controller','def resume','def reset',
                  'def reopen_writer','os.system','os.exec','LOCK_UN'):
    assert forbidden not in source
print('PASS host witness: SQLite FULL immutable binding, prior-key Ed25519 signature, nonce/observation separation, conflicts/fault freeze, explicit read-only restart and SIGKILL; no deployment/admission/device actions')
