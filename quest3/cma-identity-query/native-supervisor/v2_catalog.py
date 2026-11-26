#!/usr/bin/env python3
"""Explicit host-only observation of owner-v1/claim-v1/native-receipt-v2.

No creation, migration, admission, dispatcher, transport, cleanup or replay API.
The boot reader is injected; this library never probes a device itself.
"""
from dataclasses import asdict, dataclass, is_dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from native_receipt import MAX_RECORD, parse

MAX_OPERATIONS = 128
MAX_ENTRIES = 2*MAX_OPERATIONS+2
BOOT = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
FIELDS = ('boot', 'attempt', 'operation', 'action_sha256', 'module_sha256')


class Rejected(ValueError):
    pass


@dataclass(frozen=True)
class Expected:
    boot: str
    attempt: str
    operation: str
    action_sha256: str
    module_sha256: str


def _expected(operations):
    if not isinstance(operations, (list, tuple)) or not 0 < len(operations) <= MAX_OPERATIONS:
        raise Rejected('bounded nonempty expected manifest required')
    items = {}
    session = None
    for operation in operations:
        if not is_dataclass(operation) or isinstance(operation, type):
            raise Rejected('expected intent must be a data record')
        value = asdict(operation)
        if set(value) != set(FIELDS):
            raise Rejected('unexpected intent fields')
        for name in FIELDS:
            pattern = BOOT if name == 'boot' else r'[0-9a-f]{64}' if name.endswith('sha256') else r'[0-9a-f]{32}'
            if not isinstance(value[name], str) or not re.fullmatch(pattern, value[name]):
                raise Rejected('invalid expected identity')
        item = Expected(**value)
        key = (item.boot, item.attempt, item.module_sha256)
        if session is not None and session != key or item.operation in items:
            raise Rejected('mixed session or duplicate operation')
        session = key
        items[item.operation] = item
    return items


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode('ascii')


def _stamp(info):
    # atime is intentionally excluded: observation may itself update it.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _private(info, *, directory=False):
    if ((not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode)) or
            stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600) or
            info.st_uid != os.geteuid() or not directory and info.st_nlink != 1):
        raise Rejected('unexpected object type, permissions, owner or links')


def _names(root):
    # A separate open description avoids reusing a directory stream offset.
    fd = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root)
    try:
        result = set()
        with os.scandir(fd) as entries:
            for entry in entries:
                result.add(entry.name)
                if len(result) > MAX_ENTRIES:
                    raise Rejected('catalogue entry limit exceeded')
        return result
    finally:
        os.close(fd)


def observe(path, pinned_identity, expected_operations, *, boot_reader):
    """Observe an existing store; never authorize or send the next command.

    expected_operations is an explicit local manifest, not discovered from the
    remote catalogue. A successful result is a bounded observation, not proof of
    historical order, tree quiescence or a still-free lease after return.
    """
    result = dict(profile='owner1-claim1-native2-observation-only', state='unknown',
                  catalog_verified=False, exclusive_observation_acquired=False,
                  boot_samples_matched=False, receipts={}, unresolved=[], not_observed=[],
                  sequence_verified=False, bootstrap_verified=False,
                  original_response_verified=False, publication_durability_verified=False,
                  safe_to_mutate=False, replay_permitted=False, cleanup_permitted=False,
                  automatic_resume_allowed=False, tree_quiescence_proven=False,
                  ownership_acquired=False, boot_ready=False)
    root = lease = None
    try:
        expected = _expected(expected_operations)
        first = next(iter(expected.values()))
        if (not isinstance(pinned_identity, (tuple, list)) or len(pinned_identity) != 4 or
                any(type(v) is not int or v < 0 for v in pinned_identity) or not callable(boot_reader)):
            raise Rejected('prior directory/lease pins and boot reader required')
        pins = tuple(pinned_identity)
        if boot_reader() != first.boot:
            raise Rejected('initial boot sample mismatch')
        path = Path(path)
        root_info = path.lstat()
        _private(root_info, directory=True)
        if (root_info.st_dev, root_info.st_ino) != pins[:2]:
            raise Rejected('root path identity mismatch')
        root = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        if _stamp(os.fstat(root)) != _stamp(root_info):
            raise Rejected('root changed during open')
        lease_info = os.stat('lease.lock', dir_fd=root, follow_symlinks=False)
        _private(lease_info)
        if (lease_info.st_dev, lease_info.st_ino) != pins[2:]:
            raise Rejected('lease path identity mismatch')
        lease = os.open('lease.lock', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=root)
        if _stamp(os.fstat(lease)) != _stamp(lease_info):
            raise Rejected('lease changed during open')
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            result['state'] = 'lease-held'
            return result
        snapshots = {'lease.lock': _stamp(lease_info)}

        def read(name, limit):
            before = os.stat(name, dir_fd=root, follow_symlinks=False)
            _private(before)
            if before.st_size > limit:
                raise Rejected('record exceeds bounded observation size')
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=root)
            try:
                if _stamp(os.fstat(fd)) != _stamp(before):
                    raise Rejected('record changed during open')
                blocks, length = [], 0
                while True:
                    block = os.read(fd, min(8192, limit+1-length))
                    if not block:
                        break
                    length += len(block)
                    if length > limit:
                        raise Rejected('record grew beyond bound')
                    blocks.append(block)
                if (_stamp(os.fstat(fd)) != _stamp(before) or
                        _stamp(os.stat(name, dir_fd=root, follow_symlinks=False)) != _stamp(before)):
                    raise Rejected('record changed during read')
                snapshots[name] = _stamp(before)
                return b''.join(blocks)
            finally:
                os.close(fd)

        names = _names(root)
        allowed = {'lease.lock', 'owner.json'}
        for operation in expected:
            allowed.update(('claim-'+operation+'.json', 'done-'+operation+'.json'))
        if not {'lease.lock', 'owner.json'} <= names or not names <= allowed:
            raise Rejected('missing owner, unexpected operation or incomplete publication')
        owner = dict(schema=1, boot=first.boot, attempt=first.attempt, module_sha256=first.module_sha256,
                     root_dev=pins[0], root_ino=pins[1], lease_dev=pins[2], lease_ino=pins[3])
        if read('owner.json', 2048) != _canonical(owner):
            raise Rejected('owner bytes/schema/context mismatch')
        receipts, unresolved, missing = {}, [], []
        for operation, item in expected.items():
            claim_name, done_name = 'claim-'+operation+'.json', 'done-'+operation+'.json'
            if claim_name not in names:
                if done_name in names:
                    raise Rejected('orphan receipt')
                missing.append(operation)
                continue
            if read(claim_name, 2048) != _canonical(dict(schema=1, intent=asdict(item))):
                raise Rejected('claim bytes/schema/context mismatch')
            if done_name not in names:
                unresolved.append(operation)
                continue
            raw = read(done_name, MAX_RECORD-1)
            decoded = parse(raw, item)
            receipts[operation] = dict(receipt_sha256=hashlib.sha256(raw).hexdigest(), result=decoded)
        if boot_reader() != first.boot:
            raise Rejected('final boot sample mismatch')
        # Detect observed races even with a noncooperating writer. Not an atomic
        # guarantee against another root, ABA, or mutation after this function.
        if (_stamp(os.fstat(root)) != _stamp(root_info) or _stamp(path.lstat()) != _stamp(root_info) or
                _stamp(os.fstat(lease)) != _stamp(lease_info) or _names(root) != names):
            raise Rejected('root/lease/catalogue changed during observation')
        for name, stamp in snapshots.items():
            if _stamp(os.stat(name, dir_fd=root, follow_symlinks=False)) != stamp:
                raise Rejected('record replaced/changed before final check')
        result.update(state='claims-unresolved' if unresolved else 'partial-catalog' if missing else 'receipts-observed',
                      catalog_verified=True, exclusive_observation_acquired=True, boot_samples_matched=True,
                      receipts=receipts, unresolved=unresolved, not_observed=missing)
        return result
    except Exception as error:
        # No partial positive catalogue survives a late error. Do not expose
        # raw paths, UUIDs or receipt contents in the failure diagnostic.
        result['error_kind'] = type(error).__name__
        return result
    finally:
        if lease is not None:
            os.close(lease)  # Close only this observer's description, never LOCK_UN.
        if root is not None:
            os.close(root)
