#!/usr/bin/env python3
"""Host filesystem reference for immutable receipts/leases, NOT a device helper.

No dispatcher, subprocess, ADB, reset or cleanup API is provided. A trusted
supervisor must wait for the reviewed foreground action before Ticket.complete.
Receipts never grant permission to resume, delete files or unload a module.
"""
import base64
from dataclasses import dataclass, asdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid


MAX_STDOUT = 65536
MAX_JSON = 100000
HEX32 = r'[0-9a-f]{32}'
HEX64 = r'[0-9a-f]{64}'
BOOT = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


class Blocked(RuntimeError):
    pass


@dataclass(frozen=True)
class Intent:
    boot: str
    attempt: str
    operation: str
    action_sha256: str
    module_sha256: str

    def __post_init__(self):
        for field, pattern in (('boot', BOOT), ('attempt', HEX32), ('operation', HEX32),
                               ('action_sha256', HEX64), ('module_sha256', HEX64)):
            value = getattr(self, field)
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise ValueError('invalid intent field: ' + field)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


class ReceiptStore:
    """One persistent session per pinned private directory; no stale takeover.

    Parent directories must be trusted. Path replacement by another privileged
    actor is not prevented; dir-fd operations and the pinned identity fail closed
    on observed replacement. This reference is tested on host Linux only.
    """

    @classmethod
    def create(cls, path):
        path = Path(path)
        path.mkdir(mode=0o700, exist_ok=False)
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            lock = os.open('lease.lock', os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
                           0o600, dir_fd=fd)
            try:
                os.fsync(lock)
                lock_info = os.fstat(lock)
            finally:
                os.close(lock)
            os.fsync(fd)
            parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
            info = os.fstat(fd)
            identity = (info.st_dev, info.st_ino, lock_info.st_dev, lock_info.st_ino)
        finally:
            os.close(fd)
        return cls(path, identity)

    def __init__(self, path, expected_identity):
        if (not isinstance(expected_identity, (tuple, list)) or len(expected_identity) != 4 or
                any(type(value) is not int or value < 0 for value in expected_identity)):
            raise ValueError('invalid pinned directory/lease identity')
        self.path = Path(path)
        self.fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.poisoned = False
        self.identity = tuple(expected_identity)
        try:
            self._check_root()
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _check_root(self):
        if self.fd is None or self.poisoned:
            raise Blocked('closed store or durability failure latched')
        info = os.fstat(self.fd)
        path_info = self.path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or
                info.st_uid != os.geteuid() or (info.st_dev, info.st_ino) != self.identity[:2] or
                (path_info.st_dev, path_info.st_ino) != self.identity[:2] or
                not stat.S_ISDIR(path_info.st_mode)):
            raise Blocked('private directory identity/owner/mode mismatch')

    def _check_file(self, fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or
                info.st_uid != os.geteuid() or info.st_nlink != 1):
            raise Blocked('unexpected file type, permissions, owner or links')

    def _lock(self):
        self._check_root()
        fd = os.open('lease.lock', os.O_RDWR | os.O_NOFOLLOW, dir_fd=self.fd)
        try:
            self._check_file(fd)
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != self.identity[2:]:
                raise Blocked('lease inode was replaced; no takeover')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _read(self, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        try:
            self._check_file(fd)
            chunks, total = [], 0
            while True:
                chunk = os.read(fd, min(8192, MAX_JSON+1-total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_JSON:
                    raise Blocked('oversized receipt/claim')
            return json.loads(b''.join(chunks), object_pairs_hook=_unique_pairs)
        finally:
            os.close(fd)

    def _publish(self, name, value):
        """Exclusive publication; any uncertain stage is retained, never replaced."""
        self._check_root()
        data = (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()
        if len(data) > MAX_JSON:
            raise ValueError('record too large')
        stage = 'stage-'+uuid.uuid4().hex+'.json'
        try:
            fd = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                         0o600, dir_fd=self.fd)
            try:
                position = 0
                while position < len(data):
                    written = os.write(fd, data[position:])
                    if written <= 0:
                        raise OSError('short publication write')
                    position += written
                os.fsync(fd)
            finally:
                os.close(fd)
            # link is no-replace. A crash before stage retirement leaves a
            # visible stage/multiple links, which block admission/recovery.
            os.link(stage, name, src_dir_fd=self.fd, dst_dir_fd=self.fd, follow_symlinks=False)
            os.fsync(self.fd)
            os.unlink(stage, dir_fd=self.fd)
            os.fsync(self.fd)
        except BaseException:
            self.poisoned = True
            raise

    def _owner(self, intent):
        return dict(schema=1, boot=intent.boot, attempt=intent.attempt,
                    module_sha256=intent.module_sha256,
                    root_dev=self.identity[0], root_ino=self.identity[1],
                    lease_dev=self.identity[2], lease_ino=self.identity[3])

    def _catalog(self, intent, *, initialize=False):
        names = set(os.listdir(self.fd))
        allowed = r'(?:claim|done)-'+HEX32+r'\.json'
        if any(name not in ('lease.lock', 'owner.json') and not re.fullmatch(allowed, name) for name in names):
            raise Blocked('unknown entry or incomplete publication; retain for review')
        if 'owner.json' not in names:
            if names != {'lease.lock'}:
                raise Blocked('records without session owner')
            if not initialize:
                return {}, {}
            self._publish('owner.json', self._owner(intent))
        else:
            owner = self._read('owner.json')
            if (not isinstance(owner, dict) or type(owner.get('schema')) is not int or
                    any(type(owner.get(key)) is not int for key in
                        ('root_dev', 'root_ino', 'lease_dev', 'lease_ino')) or
                    owner != self._owner(intent)):
                raise Blocked('foreign session, boot, module or directory identity')
        claims, done = {}, {}
        for name in sorted(names):
            if name.startswith('claim-'):
                operation = name[6:-5]
                raw = self._read(name)
                if (not isinstance(raw, dict) or set(raw) != {'schema', 'intent'} or
                        type(raw['schema']) is not int or raw['schema'] != 1):
                    raise Blocked('invalid claim')
                item = Intent(**raw['intent'])
                if item.operation != operation or self._owner(item) != self._owner(intent):
                    raise Blocked('claim identity mismatch')
                claims[operation] = item
        for name in sorted(names):
            if name.startswith('done-'):
                operation = name[5:-5]
                if operation not in claims:
                    raise Blocked('receipt without claim')
                value = self._read(name)
                done[operation] = self._validate_done(value, claims[operation])
        return claims, done

    @staticmethod
    def _validate_done(value, intent):
        fields = {'schema', 'intent', 'foreground_reaped', 'returncode',
                  'stdout_b64', 'stdout_size', 'stdout_sha256'}
        if (not isinstance(value, dict) or set(value) != fields or
                type(value['schema']) is not int or value['schema'] != 1 or
                value['intent'] != asdict(intent) or value['foreground_reaped'] is not True or
                type(value['returncode']) is not int or not 0 <= value['returncode'] <= 255 or
                type(value['stdout_size']) is not int or not 0 <= value['stdout_size'] <= MAX_STDOUT or
                not isinstance(value['stdout_b64'], str)):
            raise Blocked('invalid completion receipt')
        data = base64.b64decode(value['stdout_b64'], validate=True)
        if len(data) != value['stdout_size'] or hashlib.sha256(data).hexdigest() != value['stdout_sha256']:
            raise Blocked('receipt output length/hash mismatch')
        return dict(returncode=value['returncode'], stdout=data)

    def claim(self, intent):
        fd = self._lock()
        try:
            claims, done = self._catalog(intent, initialize=True)
            if intent.operation in claims:
                raise Blocked('operation already claimed; NEVER replay, even if completed')
            if set(claims) != set(done):
                raise Blocked('unresolved prior action; new nonce does not permit bypass')
            self._publish('claim-'+intent.operation+'.json', dict(schema=1, intent=asdict(intent)))
            return Ticket(self, fd, intent)
        except BaseException:
            os.close(fd)
            raise

    def observe(self, intent):
        """Read-only classification, never an admission/cleanup authorization."""
        result = dict(state='unknown', receipt_recovered=False, safe_to_mutate=False,
                      automatic_resume_allowed=False, tree_quiescence_proven=False,
                      ownership_acquired=False, boot_ready=False)
        try:
            fd = self._lock()
        except BlockingIOError:
            result['state'] = 'lease-held'
            return result
        try:
            claims, done = self._catalog(intent)
            if intent.operation not in claims:
                result['state'] = ('other-claim-without-receipt' if set(claims) != set(done)
                                   else 'not-claimed-observation-only')
            elif claims[intent.operation] != intent:
                raise Blocked('requested operation/action differs from stored claim')
            elif intent.operation in done:
                result.update(state='completed-foreground', receipt_recovered=True,
                              **done[intent.operation])
            else:
                result['state'] = 'claim-without-receipt'
            return result
        except (OSError, ValueError, TypeError, RecursionError, Blocked) as error:
            result['reason'] = str(error)
            return result
        finally:
            os.close(fd)  # NEVER LOCK_UN: a reviewed child may share the description.


class Ticket:
    def __init__(self, store, fd, intent):
        self.store, self.fd, self.intent = store, fd, intent
        self.completed = False
        self.failed = False

    def complete(self, returncode, stdout):
        """Caller assertion after wait/reap of the reviewed foreground action.

        This library does NOT run/wait/kill actions or infer completion from PID
        disappearance. A future trusted supervisor must implement that contract.
        """
        if self.fd is None or self.completed or self.failed:
            raise Blocked('closed/completed ticket')
        if type(returncode) is not int or not 0 <= returncode <= 255 or not isinstance(stdout, bytes) or len(stdout) > MAX_STDOUT:
            self.failed = True  # Do not relabel/truncate an invalid observed outcome.
            raise ValueError('invalid foreground outcome')
        value = dict(schema=1, intent=asdict(self.intent), foreground_reaped=True,
                     returncode=returncode, stdout_b64=base64.b64encode(stdout).decode('ascii'),
                     stdout_size=len(stdout), stdout_sha256=hashlib.sha256(stdout).hexdigest())
        self.store._publish('done-'+self.intent.operation+'.json', value)
        self.completed = True

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()
