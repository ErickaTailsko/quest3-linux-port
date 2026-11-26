#!/usr/bin/env python3
"""One-lifetime HOST monitor store: durable claim BEFORE signing, no writer reopen.

SQLite/fsync fixtures do not establish independent storage or anti-rollback.
Readonly restart inspection never imports a new anchor or recovers a writer.
Keys, parent pins and genesis/latest anchors must come from a prior trusted caller.
"""
import fcntl
import os
from pathlib import Path
import sqlite3

import bootstrap_receipt as b
import bootstrap_witness_reference as w
import witness_log_monitor as m

NAME='q3-monitor-anchor'


def _identity(info): return (info.st_dev,info.st_ino)


def _names(fd):
    scan=os.open('.',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
    try:
        result=set()
        with os.scandir(scan) as entries:
            for entry in entries:
                result.add(entry.name)
                if len(result)>2: raise w.Frozen('extra/incomplete monitor store files')
        return result
    finally: os.close(scan)


class HostMonitorStore:
    """Single-threaded fixture writer; failed predecessors are never retried.

    Existing root is a terminal create barrier. The only reopen API is a
    read-only observer requiring prior store pins and an anchored genesis.
    """

    @classmethod
    def create(cls,parent_path,parent_pins,monitor_key,witness_public,log_public,genesis,held_genesis_sha256,*,fault=None):
        return cls._open(parent_path,parent_pins,witness_public,log_public,w.public_bytes(monitor_key),
                         genesis,held_genesis_sha256,monitor_key,None,fault)

    @classmethod
    def open_observer(cls,parent_path,parent_pins,store_pins,witness_public,log_public,monitor_public,
                      genesis,held_genesis_sha256):
        return cls._open(parent_path,parent_pins,witness_public,log_public,monitor_public,
                         genesis,held_genesis_sha256,None,w._pins(store_pins,6),None)

    @classmethod
    def _open(cls,parent_path,parent_pins,wp,lp,mp,genesis,held_genesis,key,expected_pins,fault):
        _,head=m._checkpoint(genesis,wp,lp,mp)
        if head['tree_size']!=0 or w._hex(held_genesis)!=m.checkpoint_commitment(genesis):
            raise ValueError('previously anchored empty genesis required')
        self=cls.__new__(cls)
        self.parent=self.root=self.lease=self.db=None
        self.poisoned=False;self.readonly=key is None;self.key=key;self.fault=fault
        self.steps={}
        self.wp,self.lp,self.mp=wp,lp,mp
        self.genesis=genesis;self.current=genesis
        self.config=m.create_config(wp,lp,mp)
        self.parent_path=Path(parent_path);self.parent_pins=w._pins(parent_pins,2)
        try:
            info=self.parent_path.lstat();b._private(info,True)
            if _identity(info)!=self.parent_pins: raise w.Frozen('monitor parent replaced')
            self.parent=os.open(self.parent_path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            if b._stamp(os.fstat(self.parent))!=b._stamp(info): raise w.Frozen('monitor parent changed')
            if not self.readonly: os.mkdir(NAME,0o700,dir_fd=self.parent)
            self.root=os.open(NAME,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.parent)
            root_info=os.fstat(self.root);b._private(root_info,True)
            mode=os.O_RDONLY|os.O_NONBLOCK if self.readonly else os.O_RDWR|os.O_CREAT|os.O_EXCL
            self.lease=os.open('lease.lock',mode|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root)
            lease_info=os.fstat(self.lease);b._private(lease_info)
            fcntl.flock(self.lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if not self.readonly:
                fd=os.open('anchor.sqlite3',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root)
                os.close(fd)
            db_info=os.stat('anchor.sqlite3',dir_fd=self.root,follow_symlinks=False);b._private(db_info)
            self.pins=_identity(root_info)+_identity(lease_info)+_identity(db_info)
            if self.readonly and self.pins!=expected_pins: raise w.Frozen('monitor store pins mismatch')
            self._check()
            uri='file:/proc/self/fd/'+str(self.root)+'/anchor.sqlite3?mode='+('ro' if self.readonly else 'rw')
            self.db=sqlite3.connect(uri,uri=True,isolation_level=None,timeout=0)
            self.db.execute('PRAGMA trusted_schema=OFF')
            if self.readonly: self.db.execute('PRAGMA query_only=ON')
            else:
                if self.db.execute('PRAGMA journal_mode=DELETE').fetchone()!=('delete',): raise w.Frozen('wrong SQLite journal mode')
                self.db.execute('PRAGMA synchronous=FULL')
                if self.db.execute('PRAGMA synchronous').fetchone()!=(2,): raise w.Frozen('FULL sync absent')
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute('CREATE TABLE identity (id INTEGER PRIMARY KEY CHECK(id=1), config BLOB, genesis BLOB)')
                self.db.execute('INSERT INTO identity VALUES (1,?,?)',(self.config,genesis))
                self.db.execute('CREATE TABLE head (id INTEGER PRIMARY KEY CHECK(id=1), checkpoint BLOB NOT NULL)')
                self.db.execute('INSERT INTO head VALUES (1,?)',(genesis,))
                self.db.execute('CREATE TABLE steps (predecessor TEXT PRIMARY KEY, prepared BLOB NOT NULL, checkpoint BLOB)')
                self.db.execute('COMMIT')
                os.fsync(self.lease);os.fsync(self.root);os.fsync(self.parent)
            self._check()
            return self
        except BaseException:
            self.poisoned=True;self.close();raise

    def _check(self):
        if self.poisoned or self.root is None: raise w.Frozen('closed/frozen monitor store')
        for fd,path_info,pins,directory in (
                (self.parent,self.parent_path.lstat(),self.parent_pins,True),
                (self.root,os.stat(NAME,dir_fd=self.parent,follow_symlinks=False),self.pins[:2],True),
                (self.lease,os.stat('lease.lock',dir_fd=self.root,follow_symlinks=False),self.pins[2:4],False)):
            info=os.fstat(fd);b._private(info,directory);b._private(path_info,directory)
            if _identity(info)!=pins or _identity(path_info)!=pins: raise w.Frozen('monitor store identity changed')
        info=os.stat('anchor.sqlite3',dir_fd=self.root,follow_symlinks=False);b._private(info)
        if _identity(info)!=self.pins[4:] or _names(self.root)!={'lease.lock','anchor.sqlite3'}:
            raise w.Frozen('monitor database replaced or incomplete transaction')
        if self.db is not None:
            if (self.db.execute('SELECT id,length(config),length(genesis) FROM identity').fetchall()!=
                    [(1,len(self.config),len(self.genesis))] or
                    self.db.execute('SELECT id,config,genesis FROM identity').fetchall()!=[(1,self.config,self.genesis)]):
                raise w.Frozen('monitor identity/genesis changed')
            sizes=self.db.execute('SELECT length(prepared),length(checkpoint) FROM steps LIMIT ?',
                                  (m.MAX_ENTRIES+1,)).fetchall()
            if (len(sizes)>m.MAX_ENTRIES or any(type(a) is not int or not 0<a<m.LIMIT or
                    c is not None and (type(c) is not int or not 0<c<m.LIMIT) for a,c in sizes)):
                raise w.Frozen('oversized/invalid monitor records')
            heads=self.db.execute('SELECT id,length(checkpoint) FROM head').fetchall()
            if len(heads)!=1 or heads[0][0]!=1 or type(heads[0][1]) is not int or not 0<heads[0][1]<m.LIMIT:
                raise w.Frozen('invalid monitor head size')
            if not self.readonly:
                rows=self.db.execute('SELECT predecessor,prepared,checkpoint FROM steps').fetchall()
                if len(rows)!=len(self.steps) or {r[0]:r[1:] for r in rows}!=self.steps:
                    raise w.Frozen('live monitor history changed')

    def _point(self,name):
        if self.fault is not None: self.fault(name)

    def _require(self,head,predecessor,prepared,checkpoint):
        self._check()
        if (self.db.execute('SELECT id,checkpoint FROM head').fetchall()!=[(1,head)] or
                self.db.execute('SELECT prepared,checkpoint FROM steps WHERE predecessor=?',(predecessor,)).fetchone()!=(prepared,checkpoint)):
            raise w.Frozen('monitor claim/head changed')

    def close(self):
        if self.db is not None: self.db.close();self.db=None
        for name in ('lease','root','parent'):
            fd=getattr(self,name,None)
            if fd is not None: os.close(fd);setattr(self,name,None)

    def advance(self,new_log_head,complete_entries,held_checkpoint_sha256):
        """Validate -> durable unique predecessor claim -> sign -> durable head.

        Any uncertainty freezes this handle. No signed checkpoint is returned
        before final publication; disk observation never proves the old return.
        """
        try:
            self._check()
            if self.readonly: raise w.Frozen('observer cannot advance')
            if w.public_bytes(self.key)!=self.mp: raise w.Frozen('monitor signing key changed')
            if self.db.execute('SELECT id,checkpoint FROM head').fetchall()!=[(1,self.current)]:
                raise w.Frozen('live monitor head changed')
            prepared=m.prepare_monitor_extension(self.wp,self.lp,self.mp,self.current,
                held_checkpoint_sha256,new_log_head,complete_entries)
            old=self.current;predecessor=m.checkpoint_commitment(old)
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('SELECT count(*) FROM steps').fetchone()[0]>=m.MAX_ENTRIES:
                raise w.Frozen('monitor step capacity reached')
            self.db.execute('INSERT INTO steps VALUES (?,?,NULL)',(predecessor,prepared))
            self._point('claim-before-commit');self.db.execute('COMMIT')
            self.steps[predecessor]=(prepared,None)
            self._point('claim-after-commit')
            self._point('claim-directory-fsync');os.fsync(self.root)
            self._require(old,predecessor,prepared,None)
            self._point('before-sign');self._require(old,predecessor,prepared,None)
            checkpoint=m._sign(self.key,b'MONITOR-CHECKPOINT',prepared)
            self._point('after-sign');self._require(old,predecessor,prepared,None)
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('UPDATE head SET checkpoint=? WHERE id=1 AND checkpoint=?',(checkpoint,old)).rowcount!=1:
                raise w.Frozen('monitor compare-and-swap failed')
            if self.db.execute('UPDATE steps SET checkpoint=? WHERE predecessor=? AND prepared=? AND checkpoint IS NULL',
                               (checkpoint,predecessor,prepared)).rowcount!=1:
                raise w.Frozen('monitor predecessor claim changed')
            self._point('checkpoint-before-commit');self.db.execute('COMMIT')
            self.steps[predecessor]=(prepared,checkpoint)
            self._point('checkpoint-after-commit')
            self._point('checkpoint-directory-fsync');os.fsync(self.root)
            self._require(checkpoint,predecessor,prepared,checkpoint)
            m._checkpoint(checkpoint,self.wp,self.lp,self.mp)
            self._point('before-return');self._require(checkpoint,predecessor,prepared,checkpoint)
            self.current=checkpoint
            return checkpoint
        except BaseException:
            self.poisoned=True;raise

    def inspect(self,held_latest_checkpoint_sha256):
        """Explicit read-only restart inspection, never a recovery/anchor import."""
        try:
            self._check()
            if not self.readonly: raise w.Frozen('inspection requires separate read-only observer')
            w._hex(held_latest_checkpoint_sha256)
            rows=self.db.execute('SELECT predecessor,prepared,checkpoint FROM steps LIMIT ?',
                                 (m.MAX_ENTRIES+1,)).fetchall()
            if len(rows)>m.MAX_ENTRIES: raise w.Frozen('oversized monitor history')
            records={row[0]:row[1:] for row in rows}
            if len(records)!=len(rows): raise w.Frozen('duplicate monitor predecessor')
            cursor=self.genesis;old_head=m._checkpoint(cursor,self.wp,self.lp,self.mp)[1]
            anchors={m.checkpoint_commitment(cursor)};visited=set();complete=0;pending=False
            while m.checkpoint_commitment(cursor) in records:
                predecessor=m.checkpoint_commitment(cursor)
                if predecessor in visited: raise w.Frozen('monitor history cycle')
                visited.add(predecessor);prepared,checkpoint=records[predecessor]
                value=b._parse(prepared,m.LIMIT)
                head=value['log_head_ascii'].encode('ascii');h=m._head(head,self.wp,self.lp,self.mp)
                expected=m._checkpoint_payload(self.config,head,value['distinct_bindings'],value['binding_map_sha256'],predecessor)
                if (prepared!=expected or not old_head['tree_size']<h['tree_size'] or
                        not 1<=value['distinct_bindings']<=h['tree_size']):
                    raise w.Frozen('monitor prepared intent mismatch')
                if checkpoint is None:
                    pending=True;break
                m._checkpoint(checkpoint,self.wp,self.lp,self.mp)
                if m._unseal(checkpoint,self.mp,b'MONITOR-CHECKPOINT')!=prepared:
                    raise w.Frozen('checkpoint does not match prior intent')
                cursor=checkpoint;old_head=h;complete+=1;anchors.add(m.checkpoint_commitment(cursor))
            if (len(visited)!=len(records) or self.db.execute('SELECT id,checkpoint FROM head').fetchall()!=[(1,cursor)] or
                    held_latest_checkpoint_sha256 not in anchors):
                raise w.Frozen('forked/foreign history, rolled-back head or caller anchor missing')
            self._check()
            latest=m.checkpoint_commitment(cursor)
            return dict(state='claim-observed-no-recovery' if pending else
                'held-anchor-matches-no-resume' if latest==held_latest_checkpoint_sha256 else
                'unacknowledged-descendant-observed-no-resume',complete_steps=complete,
                pending_claim_observed=pending,latest_observed_checkpoint_sha256=latest,
                full_prefix_rechecked_here=False,original_return_verified=False,**m.flags())
        except BaseException:
            self.poisoned=True;raise
