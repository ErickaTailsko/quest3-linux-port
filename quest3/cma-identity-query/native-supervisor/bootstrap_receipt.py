#!/usr/bin/env python3
"""Host-only bootstrap byte checks/observation. No creation, pin import or activation."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT_NAME = 'q3-identity-registry'
PROFILE = 'q3-bootstrap-host-reference-v1'
FIELDS = {'schema', 'profile', 'execution_enabled', 'attempt', 'authorization_sha256', 'boot',
          'bootstrap_operation', 'device_binding_sha256', 'helper_sha256', 'local_intent_sha256',
          'module_sha256', 'parent_dev', 'parent_ino'}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode('ascii')


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate bootstrap key')
        result[key] = value
    return result


def _parse(data, limit):
    if not isinstance(data, bytes) or not 0 < len(data) < limit:
        raise ValueError('bootstrap bytes/size mismatch')
    try:
        value = json.loads(data, object_pairs_hook=pairs)
        if not isinstance(value, dict) or canonical(value) != data:
            raise ValueError('noncanonical bootstrap record')
    except (RecursionError, UnicodeError, TypeError, OverflowError) as error:
        raise ValueError('bootstrap encoding mismatch') from error
    return value


def _uint(value, lower=0):
    if type(value) is not int or not lower <= value < 1 << 64:
        raise ValueError('bootstrap integer/type mismatch')
    return value


def parse_request(data):
    value = _parse(data, 2048)
    if (set(value) != FIELDS or type(value['schema']) is not int or value['schema'] != 1 or
            value['profile'] != PROFILE or value['execution_enabled'] is not False):
        raise ValueError('bootstrap profile/schema mismatch')
    for field in FIELDS:
        if field.endswith('sha256') or field in ('attempt', 'bootstrap_operation'):
            size = 64 if field.endswith('sha256') else 32
            if not isinstance(value[field], str) or not re.fullmatch('[0-9a-f]{'+str(size)+'}', value[field]):
                raise ValueError('bootstrap digest/nonce mismatch')
    if (not isinstance(value['boot'], str) or
            not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value['boot']) or
            value['attempt'] == value['bootstrap_operation']):
        raise ValueError('bootstrap boot/nonce mismatch')
    _uint(value['parent_dev']); _uint(value['parent_ino'], 1)
    return value


def request_commitment(data):
    parse_request(data)
    return hashlib.sha256(b'ERIS-Q3-BOOTSTRAP-HOST-V1\0'+data).hexdigest()


def parse_receipt(data, expected_request):
    request = parse_request(expected_request)
    value = _parse(data, 4096)
    try:
        pins = [_uint(value[key], 0 if key.endswith('dev') else 1)
                for key in ('root_dev', 'root_ino', 'lease_dev', 'lease_ino')]
    except KeyError as error:
        raise ValueError('bootstrap pins missing') from error
    expected = dict(admission_enabled=False, bootstrap_phase='metadata-only-no-activation', execution_enabled=False,
                    lease_dev=pins[2], lease_ino=pins[3], local_pin_ack_verified=False,
                    producer='host-native-bootstrap-reference', profile=PROFILE, request=request,
                    request_sha256=request_commitment(expected_request), root_dev=pins[0], root_ino=pins[1], schema=1)
    if (canonical(expected) != data or pins[0] != request['parent_dev'] or pins[2] != pins[0] or
            len({request['parent_ino'], pins[1], pins[3]}) != 3):
        raise ValueError('bootstrap metadata/context/pin mismatch')
    return dict(state='metadata-observed-no-activation', metadata_matches_request=True,
                candidate_pins=pins, request_sha256=request_commitment(expected_request),
                receipt_sha256=hashlib.sha256(data).hexdigest(), pin_import_permitted=False,
                local_pin_ack_verified=False, authorization_verified=False, bootstrap_verified=False,
                original_response_verified=False, publication_durability_verified=False,
                execution_enabled=False, admission_enabled=False, safe_to_mutate=False,
                replay_permitted=False, cleanup_permitted=False, automatic_resume_allowed=False)


def reply_matches(data, expected_request, receipt_sha256):
    request = parse_request(expected_request)
    if not isinstance(receipt_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', receipt_sha256):
        raise ValueError('invalid expected receipt digest')
    expected = ('ERIS_BOOTSTRAP_RECEIPT '+request['bootstrap_operation']+' '+receipt_sha256+'\n').encode('ascii')
    if not isinstance(data, bytes) or data != expected:
        raise ValueError('missing/truncated/foreign bootstrap reply')
    return True  # Byte equality ONLY, not durable local pin acknowledgment.


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _private(info, directory=False):
    if ((not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode)) or
            stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600) or
            info.st_uid != os.geteuid() or not directory and info.st_nlink != 1):
        raise ValueError('unexpected bootstrap object type/owner/permissions/links')


def observe(parent_path, parent_pins, expected_request, *, boot_reader):
    """Propose metadata for review under a prior parent anchor; NEVER import pins.

    No transport, existing-controller integration, cleanup or retry is included.
    Matching receipts from a private directory are not producer authentication.
    """
    result = dict(state='unknown', metadata_matches_request=False, candidate_pins=None,
                  pin_import_permitted=False, local_pin_ack_verified=False, bootstrap_verified=False,
                  authorization_verified=False, original_response_verified=False,
                  publication_durability_verified=False, execution_enabled=False, admission_enabled=False,
                  safe_to_mutate=False, replay_permitted=False, cleanup_permitted=False,
                  automatic_resume_allowed=False)
    parent = root = lease = None
    try:
        request = parse_request(expected_request)
        if (not isinstance(parent_pins, (tuple, list)) or len(parent_pins) != 2 or
                any(type(v) is not int for v in parent_pins) or
                tuple(parent_pins) != (request['parent_dev'], request['parent_ino']) or
                not callable(boot_reader) or boot_reader() != request['boot']):
            raise ValueError('prior parent anchor/boot source mismatch')
        parent_path = Path(parent_path)
        before = parent_path.lstat(); _private(before, True)
        if (before.st_dev, before.st_ino) != tuple(parent_pins):
            raise ValueError('parent path replaced')
        parent = os.open(parent_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        if _stamp(os.fstat(parent)) != _stamp(before):
            raise ValueError('parent changed during open')
        try:
            root_before = os.stat(ROOT_NAME, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            result['state'] = 'root-not-observed'
            return result
        _private(root_before, True)
        root = os.open(ROOT_NAME, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent)
        if _stamp(os.fstat(root)) != _stamp(root_before):
            raise ValueError('root changed during open')
        lease_before = os.stat('lease.lock', dir_fd=root, follow_symlinks=False); _private(lease_before)
        lease = os.open('lease.lock', os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
        if _stamp(os.fstat(lease)) != _stamp(lease_before):
            raise ValueError('lease changed during open')
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            result['state'] = 'lease-held'
            return result
        # Fixed, bounded catalogue. Pending/foreign files are never repaired.
        def names():
            fd = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=root)
            try:
                found = set()
                with os.scandir(fd) as entries:
                    for entry in entries:
                        found.add(entry.name)
                        if len(found)>3: raise ValueError('extra/incomplete bootstrap entries')
                return found
            finally:
                os.close(fd)
        required = {'lease.lock', 'bootstrap-intent.json', 'bootstrap-receipt.json'}
        if names() != required:
            raise ValueError('incomplete bootstrap publication')
        snapshots = {'lease.lock': _stamp(lease_before)}
        def read(name, limit):
            info = os.stat(name, dir_fd=root, follow_symlinks=False); _private(info)
            if info.st_size>=limit: raise ValueError('oversized bootstrap record')
            fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
            try:
                if _stamp(os.fstat(fd)) != _stamp(info): raise ValueError('record changed during open')
                data = b''
                while len(data)<limit:
                    chunk = os.read(fd, limit-len(data))
                    if not chunk: break
                    data += chunk
                if len(data)>=limit or _stamp(os.fstat(fd)) != _stamp(info): raise ValueError('record changed during read')
                snapshots[name] = _stamp(info)
                return data
            finally:
                os.close(fd)
        if read('bootstrap-intent.json', 2048) != expected_request:
            raise ValueError('bootstrap intent differs from prior local request')
        parsed = parse_receipt(read('bootstrap-receipt.json', 4096), expected_request)
        if parsed['candidate_pins'] != [root_before.st_dev, root_before.st_ino, lease_before.st_dev, lease_before.st_ino]:
            raise ValueError('receipt pins do not match current objects')
        if boot_reader() != request['boot'] or names() != required:
            raise ValueError('boot/catalogue changed during observation')
        if (_stamp(parent_path.lstat()) != _stamp(before) or _stamp(os.fstat(parent)) != _stamp(before) or
                _stamp(os.fstat(root)) != _stamp(root_before) or
                _stamp(os.stat(ROOT_NAME,dir_fd=parent,follow_symlinks=False)) != _stamp(root_before) or
                _stamp(os.fstat(lease)) != _stamp(lease_before)):
            raise ValueError('bootstrap objects changed during observation')
        for name, stamp in snapshots.items():
            if _stamp(os.stat(name,dir_fd=root,follow_symlinks=False)) != stamp:
                raise ValueError('record replaced before final check')
        return parsed
    except Exception as error:
        result['error_kind'] = type(error).__name__
        return result
    finally:
        for fd in (lease, root, parent):
            if fd is not None: os.close(fd)
