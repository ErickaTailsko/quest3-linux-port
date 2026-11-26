#!/usr/bin/env python3
"""HOST FIXTURE witness: SQLite binding + Ed25519 statements, no network/actions.

Same-host tests do NOT establish a separate trust domain or production durability.
Keys are injected fixtures; provisioning, service deployment and controller
integration are deliberately absent. Reopening permits observation only.
"""
import base64
import fcntl
import hashlib
import os
from pathlib import Path
import re
import sqlite3

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import bootstrap_receipt as b

NAME='q3-bootstrap-witness'
PROFILE='q3-bootstrap-witness-host-reference-v1'
LIMIT=16384
MAX_BINDINGS=128


class Frozen(RuntimeError):
    pass


def flags():
    return dict(execution_enabled=False,admission_enabled=False,pin_import_permitted=False,
                local_pin_ack_verified=False,bootstrap_verified=False,authorization_verified=False,
                publication_durability_verified=False,automatic_resume_allowed=False,
                replay_permitted=False,cleanup_permitted=False,safe_to_mutate=False,
                controller_integrated=False)


def _hash(role,data):
    return hashlib.sha256(b'ERIS-Q3-BOOTSTRAP-WITNESS-HOST-V1\0'+role+b'\0'+data).hexdigest()


def _hex(value,size=64):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(size)+'}',value):
        raise ValueError('invalid witness identifier/digest')
    return value


def public_bytes(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)


def _key_id(raw):
    if not isinstance(raw,bytes) or len(raw)!=32: raise ValueError('prior raw Ed25519 key required')
    return _hash(b'KEY',raw)


def create_request(pending_sha256,checkpoint_sha256,context_sha256,nonce):
    return b.canonical(dict(schema=1,profile=PROFILE,kind='notarize-checkpoint-digest',
        pending_sha256=_hex(pending_sha256),checkpoint_sha256=_hex(checkpoint_sha256),
        context_sha256=_hex(context_sha256),nonce=_hex(nonce,32),**flags()))


def _request(raw):
    value=b._parse(raw,LIMIT)
    try: expected=create_request(value['pending_sha256'],value['checkpoint_sha256'],value['context_sha256'],value['nonce'])
    except KeyError as error: raise ValueError('witness request shape mismatch') from error
    if expected!=raw: raise ValueError('witness request fields/profile mismatch')
    return value


def _binding(request,key_id):
    r=_request(request)
    return b.canonical(dict(schema=1,profile=PROFILE,kind='immutable-fixture-binding',
        witness_key_sha256=key_id,pending_sha256=r['pending_sha256'],
        checkpoint_sha256=r['checkpoint_sha256'],context_sha256=r['context_sha256'],**flags()))


def _payload(request,binding,key_id,observation):
    if observation not in ('publication-confirmed','record-observed'):
        raise ValueError('unknown witness observation')
    if binding!=_binding(request,key_id): raise ValueError('conflicting witness binding')
    return b.canonical(dict(schema=1,profile=PROFILE,producer='host-fixture-witness',
        observation=observation,witness_key_sha256=key_id,request=_request(request),
        request_sha256=_hash(b'REQUEST',request),binding=b._parse(binding,LIMIT),
        binding_sha256=_hash(b'BINDING',binding),**flags()))


def verify_statement(statement,request,prior_public_key,*,expected_observation):
    """Authenticate supplied bytes under a PRIOR key, not deployment/history.

    Never learn that key from the response or use this result as pin admission.
    The witness attests a digest binding, not the validity of the bootstrap,
    authorization, remote execution or receipt contents behind those digests.
    """
    key_id=_key_id(prior_public_key)
    envelope=b._parse(statement,LIMIT)
    try:
        payload=b.canonical(envelope['payload'])
        binding=b.canonical(envelope['payload']['binding'])
        signature=base64.b64decode(envelope['signature_b64'],validate=True)
    except (KeyError,TypeError) as error: raise ValueError('witness envelope shape mismatch') from error
    expected=_payload(request,binding,key_id,expected_observation)
    if (payload!=expected or len(signature)!=64 or
            b.canonical(dict(payload=b._parse(payload,LIMIT),signature_b64=base64.b64encode(signature).decode('ascii')))!=statement):
        raise ValueError('foreign/malformed witness statement')
    try:
        Ed25519PublicKey.from_public_bytes(prior_public_key).verify(
            signature,b'ERIS-Q3-WITNESS-STATEMENT-V1\0'+payload)
    except InvalidSignature as error: raise ValueError('witness signature mismatch') from error
    return dict(state='signed-fixture-binding-no-admission',signature_verified=True,
        expected_request_matched=True,observation=expected_observation,
        binding_sha256=_hash(b'BINDING',binding),witness_key_sha256=key_id,
        witness_deployment_independence_verified=False,original_response_delivery_verified=False,
        witness_rollback_protection_verified=False,witness_non_equivocation_verified=False,
        historical_bootstrap_execution_proven=False,writer_recovered=False,**flags())


def _identity(info): return (info.st_dev,info.st_ino)


def _pins(values,count):
    if (not isinstance(values,(tuple,list)) or len(values)!=count or
            any(type(v) is not int or not 0<=v<1<<64 for v in values) or
            any(not values[i] for i in range(1,count,2))):
        raise ValueError('prior witness pins required')
    return tuple(values)


def _names(fd):
    names=set()
    # A fresh directory description also avoids reusing a catalogue cursor or
    # stale view from a descriptor opened before the entries were created.
    scan=os.open('.',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
    try:
        with os.scandir(scan) as entries:
            for entry in entries:
                names.add(entry.name)
                if len(names)>2: raise Frozen('unexpected witness files')
    finally:
        os.close(scan)
    return names


class FixtureWitness:
    """Single-threaded fixture service object; no socket, deployment or key store.

    A pending commitment has at most one checkpoint/context binding. Repeating
    the same binding is idempotent notarization, NOT replay of a device action.
    Failures freeze this handle. Only explicit read-only observation may reopen.
    """

    @classmethod
    def create(cls,parent_path,parent_pins,key,*,fault=None):
        return cls._open(parent_path,parent_pins,key,False,None,fault)

    @classmethod
    def open_observer(cls,parent_path,parent_pins,witness_pins,key,*,fault=None):
        return cls._open(parent_path,parent_pins,key,True,_pins(witness_pins,6),fault)

    @classmethod
    def _open(cls,parent_path,parent_pins,key,readonly,witness_pins,fault):
        self=cls.__new__(cls)
        self.parent=self.root=self.lease=self.db=None
        self.poisoned=False;self.readonly=readonly;self.fault=fault
        self.parent_path=Path(parent_path);self.parent_pins=_pins(parent_pins,2)
        self.key=key;self.key_id=_key_id(public_bytes(key))
        try:
            info=self.parent_path.lstat();b._private(info,True)
            if _identity(info)!=self.parent_pins: raise Frozen('witness parent replaced')
            self.parent=os.open(self.parent_path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            if b._stamp(os.fstat(self.parent))!=b._stamp(info): raise Frozen('witness parent changed')
            if not readonly: os.mkdir(NAME,0o700,dir_fd=self.parent)
            self.root=os.open(NAME,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.parent)
            root_info=os.fstat(self.root);b._private(root_info,True)
            self.lease=os.open('lease.lock',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK if readonly else
                os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root)
            lease_info=os.fstat(self.lease);b._private(lease_info)
            fcntl.flock(self.lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if not readonly:
                fd=os.open('witness.sqlite3',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root)
                os.close(fd)
            db_info=os.stat('witness.sqlite3',dir_fd=self.root,follow_symlinks=False);b._private(db_info)
            self.pins=_identity(root_info)+_identity(lease_info)+_identity(db_info)
            if readonly and self.pins!=witness_pins: raise Frozen('witness store pins mismatch')
            self._check()
            uri='file:/proc/self/fd/'+str(self.root)+'/witness.sqlite3?mode='+('ro' if readonly else 'rw')
            self.db=sqlite3.connect(uri,uri=True,isolation_level=None,timeout=0)
            self.db.execute('PRAGMA trusted_schema=OFF')
            if readonly: self.db.execute('PRAGMA query_only=ON')
            else:
                if self.db.execute('PRAGMA journal_mode=DELETE').fetchone()!=('delete',): raise Frozen('wrong journal mode')
                self.db.execute('PRAGMA synchronous=FULL')
                if self.db.execute('PRAGMA synchronous').fetchone()!=(2,): raise Frozen('FULL sync not enabled')
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute('CREATE TABLE identity (key_id TEXT NOT NULL)')
                self.db.execute('INSERT INTO identity VALUES (?)',(self.key_id,))
                self.db.execute('CREATE TABLE bindings (pending TEXT PRIMARY KEY, record BLOB NOT NULL)')
                self.db.execute('COMMIT')
                os.fsync(self.lease);os.fsync(self.root);os.fsync(self.parent)
            if self.db.execute('SELECT key_id FROM identity').fetchall()!=[(self.key_id,)]:
                raise Frozen('unreviewed witness key rotation')
            self._check()
            return self
        except BaseException:
            self.poisoned=True;self.close();raise

    def close(self):
        if self.db is not None:
            self.db.close();self.db=None
        for name in ('lease','root','parent'):
            fd=getattr(self,name,None)
            if fd is not None: os.close(fd);setattr(self,name,None)

    def _point(self,name):
        if self.fault is not None: self.fault(name)

    def _check(self):
        if self.poisoned or self.root is None: raise Frozen('closed/frozen witness')
        objects=((self.parent, self.parent_path.lstat(), self.parent_pins, True),
                 (self.root, os.stat(NAME,dir_fd=self.parent,follow_symlinks=False), self.pins[:2], True),
                 (self.lease, os.stat('lease.lock',dir_fd=self.root,follow_symlinks=False), self.pins[2:4], False))
        for fd,path_info,pins,directory in objects:
            info=os.fstat(fd);b._private(info,directory);b._private(path_info,directory)
            if _identity(info)!=pins or _identity(path_info)!=pins: raise Frozen('witness identity replaced')
        db_info=os.stat('witness.sqlite3',dir_fd=self.root,follow_symlinks=False);b._private(db_info)
        if _identity(db_info)!=self.pins[4:]: raise Frozen('witness database replaced')
        if _names(self.root)!={'lease.lock','witness.sqlite3'}: raise Frozen('incomplete witness transaction/catalogue')
        if self.db is not None and self.db.execute('SELECT key_id FROM identity').fetchall()!=[(self.key_id,)]:
            raise Frozen('witness key identity changed')

    def _check_binding(self,request,binding):
        value=_request(request)
        if self.db.execute('SELECT record FROM bindings WHERE pending=?',(value['pending_sha256'],)).fetchone()!=(binding,):
            raise Frozen('witness binding changed before statement return')

    def _sign(self,request,binding,observation):
        payload=_payload(request,binding,self.key_id,observation)
        self._point('before-sign')
        self._check()
        self._check_binding(request,binding)
        statement=b.canonical(dict(payload=b._parse(payload,LIMIT),signature_b64=base64.b64encode(
            self.key.sign(b'ERIS-Q3-WITNESS-STATEMENT-V1\0'+payload)).decode('ascii')))
        self._point('before-return')
        self._check()
        self._check_binding(request,binding)
        return statement

    def publish(self,request):
        try:
            self._check()
            if self.readonly: raise Frozen('observer cannot publish')
            value=_request(request);record=_binding(request,self.key_id)
            self.db.execute('BEGIN IMMEDIATE')
            found=self.db.execute('SELECT record FROM bindings WHERE pending=?',(value['pending_sha256'],)).fetchone()
            if found is None:
                if self.db.execute('SELECT count(*) FROM bindings').fetchone()[0]>=MAX_BINDINGS:
                    raise Frozen('bounded fixture witness capacity reached')
                self.db.execute('INSERT INTO bindings VALUES (?,?)',(value['pending_sha256'],record))
            elif found!=(record,): raise Frozen('conflicting checkpoint for an existing pending commitment')
            self._point('before-commit')
            self.db.execute('COMMIT')
            self._point('after-commit')
            self._point('directory-fsync');os.fsync(self.root)
            self._check()
            if self.db.execute('SELECT record FROM bindings WHERE pending=?',(value['pending_sha256'],)).fetchone()!=(record,):
                raise Frozen('witness record changed after commit')
            return self._sign(request,record,'publication-confirmed')
        except BaseException:
            self.poisoned=True;raise

    def lookup(self,request):
        """Explicit witness-side observation; never claims delivery of an old reply."""
        try:
            self._check();value=_request(request)
            found=self.db.execute('SELECT record FROM bindings WHERE pending=?',(value['pending_sha256'],)).fetchone()
            if found is None: raise Frozen('no witness binding observed; absence does not permit retry')
            return self._sign(request,found[0],'record-observed')
        except BaseException:
            self.poisoned=True;raise
