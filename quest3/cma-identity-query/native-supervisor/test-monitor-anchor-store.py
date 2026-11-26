#!/usr/bin/env python3
"""Durable-claim/sign ordering in private HOST stores; no services/device I/O."""
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
import witness_log_monitor as m
import monitor_anchor_store as s


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except (ValueError,w.Frozen,OSError,sqlite3.Error): pass
    else: raise AssertionError('unsafe monitor store transition accepted')


def safe(result):
    for field,value in m.flags().items(): assert result[field] is value is False
    assert not result['full_prefix_rechecked_here'] and not result['original_return_verified']
    assert 'checkpoint' not in result and 'next_checkpoint' not in result
    return result


wk=Ed25519PrivateKey.generate();lk=Ed25519PrivateKey.generate();mk=Ed25519PrivateKey.generate()
wp,lp,mp=(w.public_bytes(key) for key in (wk,lk,mk))
empty=m.sign_fixture_log_head(lk,wp,mp,[])
genesis=m.create_fixture_genesis(mk,wp,lp,empty);genesis_sha=m.checkpoint_commitment(genesis)


class CountingKey:
    def __init__(self): self.calls=0;self.hook=None
    def public_key(self): return mk.public_key()
    def sign(self,data):
        if self.hook is not None: self.hook()
        self.calls+=1
        return mk.sign(data)


with tempfile.TemporaryDirectory(prefix='q3-monitor-store-',dir=os.environ.get('Q3_MONITOR_TEST_TMP','/tmp/opencode')) as temporary:
    root=Path(temporary)

    def parent(name):
        path=root/name;path.mkdir(mode=0o700);info=path.stat()
        return path,(info.st_dev,info.st_ino)

    def entry(name,pending,checkpoint,nonce):
        path,pins=parent('entry-'+name)
        service=w.FixtureWitness.create(path,pins,wk)
        request=w.create_request(pending,checkpoint,'3'*64,nonce)
        statement=service.publish(request);service.close()
        return m.create_entry(wp,request,statement)

    a=entry('a','1'*64,'2'*64,'4'*32)
    second=entry('b','5'*64,'6'*64,'7'*32)
    conflict=entry('fork','1'*64,'8'*64,'9'*32)
    head=lambda entries:m.sign_fixture_log_head(lk,wp,mp,entries)

    def create(name,fault=None):
        path,pins=parent(name);counter=CountingKey()
        store=s.HostMonitorStore.create(path,pins,counter,wp,lp,genesis,genesis_sha,fault=fault)
        assert counter.calls==0
        return store,counter,path,pins

    def inspect(path,pins,store_pins,held):
        observer=s.HostMonitorStore.open_observer(path,pins,store_pins,wp,lp,mp,genesis,genesis_sha)
        try: return safe(observer.inspect(held))
        finally: observer.close()

    store,counter,path,pins=create('success');store_pins=store.pins
    assert store.db.execute('PRAGMA synchronous').fetchone()==(2,)
    assert store.db.execute('PRAGMA journal_mode').fetchone()==('delete',)
    denied(s.HostMonitorStore.open_observer,path,pins,store_pins,wp,lp,mp,genesis,genesis_sha)
    fsync_events=[];original_fsync=os.fsync
    def fsync(fd):
        original_fsync(fd)
        if fd==store.root: fsync_events.append('directory-synced')
    def before_actual_sign():
        assert fsync_events==['directory-synced']
        assert not store.db.in_transaction
        row=store.db.execute('SELECT predecessor,checkpoint FROM steps').fetchall()
        assert row==[(genesis_sha,None)]
    counter.hook=before_actual_sign
    with mock.patch.object(s.os,'fsync',side_effect=fsync): one=store.advance(head([a]),[a],genesis_sha)
    counter.hook=None
    assert counter.calls==1 and fsync_events==['directory-synced','directory-synced']
    assert one==m.advance_fixture_monitor(mk,wp,lp,genesis,genesis_sha,head([a]),[a])
    one_sha=m.checkpoint_commitment(one)
    two=store.advance(head([a,second]),[a,second],one_sha);two_sha=m.checkpoint_commitment(two)
    assert counter.calls==2
    assert store.db.execute('SELECT count(*) FROM steps').fetchone()==(2,)
    store.close()
    assert inspect(path,pins,store_pins,two_sha)['state']=='held-anchor-matches-no-resume'
    assert inspect(path,pins,store_pins,genesis_sha)['state']=='unacknowledged-descendant-observed-no-resume'
    denied(s.HostMonitorStore.create,path,pins,mk,wp,lp,genesis,genesis_sha)
    denied(s.HostMonitorStore.open_observer,path,pins,store_pins,wp,lp,mp,genesis,'0'*64)
    observer=s.HostMonitorStore.open_observer(path,pins,store_pins,wp,lp,mp,genesis,genesis_sha)
    denied(observer.advance,head([a]),[a],genesis_sha);assert observer.poisoned;observer.close()

    for stage in ('claim-before-commit','claim-after-commit','claim-directory-fsync','before-sign',
                  'after-sign','checkpoint-before-commit','checkpoint-after-commit',
                  'checkpoint-directory-fsync','before-return'):
        def fault(point):
            if point==stage: raise OSError('injected '+stage)
        store,counter,path,pins=create('fault-'+stage,fault);store_pins=store.pins
        denied(store.advance,head([a]),[a],genesis_sha)
        assert store.poisoned and counter.calls==(0 if stage in
            ('claim-before-commit','claim-after-commit','claim-directory-fsync','before-sign') else 1)
        with mock.patch.object(s.os,'stat',side_effect=AssertionError('read after freeze')):
            denied(store.advance,head([a]),[a],genesis_sha)
        store.close()
        result=inspect(path,pins,store_pins,genesis_sha)
        if stage=='claim-before-commit':
            assert result['state']=='held-anchor-matches-no-resume' and result['complete_steps']==0
        elif stage in ('checkpoint-after-commit','checkpoint-directory-fsync','before-return'):
            assert result['state']=='unacknowledged-descendant-observed-no-resume' and result['complete_steps']==1
        else: assert result['state']=='claim-observed-no-recovery' and result['pending_claim_observed']
        denied(s.HostMonitorStore.create,path,pins,mk,wp,lp,genesis,genesis_sha)

    # A directory fsync may complete but its return be uncertain to the caller.
    for failed_call in (1,2):
        store,counter,path,pins=create('uncertain-fsync-'+str(failed_call));store_pins=store.pins
        calls=[0]
        def uncertain_fsync(fd):
            original_fsync(fd)
            if fd==store.root:
                calls[0]+=1
                if calls[0]==failed_call: raise OSError('fsync completion uncertain')
        with mock.patch.object(s.os,'fsync',side_effect=uncertain_fsync):
            denied(store.advance,head([a]),[a],genesis_sha)
        assert store.poisoned and counter.calls==failed_call-1
        store.close();result=inspect(path,pins,store_pins,genesis_sha)
        assert result['state']==('claim-observed-no-recovery' if failed_call==1 else
                                 'unacknowledged-descendant-observed-no-resume')

    # Invalid/replayed/reordered prefixes fail before signing or consuming intent.
    for kind in ('missing-anchor','repeated-head','rewrite','appended-conflict','missing-prefix'):
        store,counter,path,pins=create('reject-'+kind)
        one=store.advance(head([a]),[a],genesis_sha);one_sha=m.checkpoint_commitment(one)
        entries=[a,second];held=one_sha;new_head=head(entries)
        if kind=='missing-anchor': held=genesis_sha
        if kind=='repeated-head': entries=[a];new_head=head(entries)
        if kind=='rewrite': entries=[conflict,second];new_head=head(entries)
        if kind=='appended-conflict': entries=[a,conflict];new_head=head(entries)
        if kind=='missing-prefix': entries=[second]
        denied(store.advance,new_head,entries,held)
        assert store.poisoned and counter.calls==1
        assert store.db.execute('SELECT count(*) FROM steps').fetchone()==(1,)
        store.close()

    # Claim/head tampering before sign and previous-history changes fail closed.
    for target in ('claim','head','identity','extra'):
        store,counter,path,pins=create('tamper-'+target)
        def corrupt(point):
            if point!='before-sign': return
            if target=='claim': store.db.execute('UPDATE steps SET prepared=?',(b'foreign',))
            elif target=='head': store.db.execute('UPDATE head SET checkpoint=?',(b'foreign',))
            elif target=='identity': store.db.execute('UPDATE identity SET config=?',(b'foreign',))
            else: (path/s.NAME/'foreign').write_bytes(b'foreign')
        store.fault=corrupt;denied(store.advance,head([a]),[a],genesis_sha)
        assert store.poisoned and counter.calls==0;store.close()

    # Restore the same database inode to an old valid snapshot. A separately held
    # latest anchor detects it; selecting an equally stale anchor cannot.
    store,counter,path,pins=create('restored-snapshot');store_pins=store.pins
    database=path/s.NAME/'anchor.sqlite3';snapshot=database.read_bytes()
    one=store.advance(head([a]),[a],genesis_sha);one_sha=m.checkpoint_commitment(one);store.close()
    database.write_bytes(snapshot)
    denied(inspect,path,pins,store_pins,one_sha)
    stale=inspect(path,pins,store_pins,genesis_sha)
    assert stale['state']=='held-anchor-matches-no-resume' and not stale['monitor_anchor_freshness_verified']
    assert not stale['witness_rollback_protection_verified']

    # SIGKILL before signing and after final COMMIT never authorizes writer reopen.
    for point,expected_signs in (('before-sign',0),('checkpoint-after-commit',1)):
        path,pins=parent('killed-'+point);left,right=socket.socketpair();pid=os.fork()
        if pid==0:
            left.close();counter=CountingKey()
            def pause(stage):
                if stage==point: right.sendall(b'R'+str(counter.calls).encode());right.recv(1)
            try:
                store=s.HostMonitorStore.create(path,pins,counter,wp,lp,genesis,genesis_sha,fault=pause)
                store.advance(head([a]),[a],genesis_sha);os._exit(3)
            except BaseException: os._exit(4)
        right.close()
        try:
            ready,_,_=select.select([left],[],[],5)
            assert ready and left.recv(2)==b'R'+str(expected_signs).encode()
            folder=path/s.NAME
            store_pins=tuple(v for item in (folder,folder/'lease.lock',folder/'anchor.sqlite3') for v in (item.stat().st_dev,item.stat().st_ino))
        finally:
            os.kill(pid,signal.SIGKILL);os.waitpid(pid,0);left.close()
        result=inspect(path,pins,store_pins,genesis_sha)
        assert result['state']==('claim-observed-no-recovery' if not expected_signs else 'unacknowledged-descendant-observed-no-resume')
        denied(s.HostMonitorStore.create,path,pins,mk,wp,lp,genesis,genesis_sha)

source=Path(s.__file__).read_text()
for forbidden in ('import socket','import subprocess','import controller','def resume','def reset','def reopen_writer','LOCK_UN'):
    assert forbidden not in source
print('PASS monitor anchor host store: durable unique predecessor intent BEFORE signing, FULL transactions/CAS head, frozen faults/SIGKILL, read-only non-recovery and external-anchor rollback limit; no deployment/device actions')
