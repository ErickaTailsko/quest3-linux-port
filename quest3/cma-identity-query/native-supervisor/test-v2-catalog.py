#!/usr/bin/env python3
"""Host files/leases plus synthetic receipt cases; no dispatcher or device I/O."""
import base64
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receipt_store import Intent, ReceiptStore
import v2_catalog as m


intent = Intent('00000000-0000-0000-0000-000000000001', 'a'*32, '1'*32, 'c'*64, 'b'*64)
other = replace(intent, operation='2'*32)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def done(item, *, stdout=b'output\n', stderr=b'diagnostic\n', status=0):
    value = dict(schema=2, intent=asdict(item), foreground_reaped=True,
                 termination_kind='exit', termination_value=status, exec_errno=0,
                 supervisor_interrupted=False, tree_quiescence_proven=False, safe_to_mutate=False)
    for stream, data in [('stdout', stdout), ('stderr', stderr)]:
        value.update({stream+'_b64': base64.b64encode(data).decode(),
                      stream+'_size': len(data), stream+'_sha256': hashlib.sha256(data).hexdigest()})
    return canonical(value)


def create(root, name, *, completed=True):
    store = ReceiptStore.create(root/name)
    ticket = store.claim(intent)
    ticket.close()
    if completed:
        write(store.path/('done-'+intent.operation+'.json'), done(intent))
    return store


def write(path, data):
    # Test fixture construction only, never part of the observer.
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(0o600)


def snapshot(path):
    return {p.name: (p.lstat().st_mode, p.lstat().st_ino,
                     p.read_bytes() if p.is_file() and not p.is_symlink() else b'NONREGULAR')
            for p in path.iterdir()}


def observed(store, operations=(intent,), *, boot_reader=lambda: intent.boot, pins=None):
    value = m.observe(store.path, store.identity if pins is None else pins, operations, boot_reader=boot_reader)
    assert all(value[key] is False for key in ('safe_to_mutate', 'replay_permitted', 'cleanup_permitted',
               'automatic_resume_allowed', 'sequence_verified', 'bootstrap_verified',
               'original_response_verified', 'publication_durability_verified',
               'tree_quiescence_proven', 'ownership_acquired', 'boot_ready'))
    if value['state'] == 'unknown':
        assert not value['receipts'] and not value['catalog_verified'] and not value['boot_samples_matched']
    return value


with tempfile.TemporaryDirectory(prefix='cma-v2-observer-', dir='/tmp/opencode') as temporary:
    root = Path(temporary)
    store = create(root, 'complete')
    before = snapshot(store.path)
    value = observed(store)
    assert value['state'] == 'receipts-observed' and value['catalog_verified']
    assert value['exclusive_observation_acquired'] and value['boot_samples_matched']
    assert value['receipts'][intent.operation]['result']['stdout'] == b'output\n'
    assert value['receipts'][intent.operation]['result']['stderr'] == b'diagnostic\n'
    assert snapshot(store.path) == before
    descriptors = len(os.listdir('/proc/self/fd'))
    for _ in range(10):
        assert observed(store)['state'] == 'receipts-observed'
    assert len(os.listdir('/proc/self/fd')) == descriptors
    assert store.observe(intent)['state'] == 'unknown'  # No implicit v1 migration.
    value = observed(store, (intent, other))
    assert value['state'] == 'partial-catalog' and value['not_observed'] == [other.operation]
    # A synthetic two-operation catalogue tests observation, NOT native admission.
    write(store.path/('claim-'+other.operation+'.json'), canonical(dict(schema=1, intent=asdict(other))))
    assert observed(store, (intent, other))['state'] == 'claims-unresolved'
    write(store.path/('done-'+other.operation+'.json'), done(other, status=23))
    value = observed(store, (intent, other))
    assert value['state'] == 'receipts-observed' and len(value['receipts']) == 2
    assert value['receipts'][other.operation]['result']['termination_value'] == 23
    reversed_manifest = observed(store, (other, intent))
    assert reversed_manifest['state'] == 'receipts-observed' and not reversed_manifest['sequence_verified']
    # Corrupt one record: even the valid first receipt is not returned as a
    # partial positive result in an invalid catalogue.
    path = store.path/('done-'+other.operation+'.json')
    path.write_bytes(b'partial')
    assert observed(store, (intent, other))['state'] == 'unknown'
    store.close()

    store = create(root, 'entry-limit')
    for number in range(m.MAX_ENTRIES+1):
        write(store.path/('extra-'+str(number)), b'')
    assert observed(store)['state'] == 'unknown'
    store.close()

    store = create(root, 'pending', completed=False)
    value = observed(store)
    assert value['state'] == 'claims-unresolved' and value['unresolved'] == [intent.operation]
    assert not value['receipts']
    store.close()

    store = ReceiptStore.create(root/'held')
    with store.claim(intent):
        value = observed(store)
        assert value['state'] == 'lease-held' and not value['catalog_verified']
    store.close()

    store = create(root, 'legacy', completed=False)
    write(store.path/('done-'+intent.operation+'.json'), canonical(dict(schema=1, intent=asdict(intent),
          foreground_reaped=True, returncode=0, stdout_b64='', stdout_size=0,
          stdout_sha256=hashlib.sha256(b'').hexdigest())))
    assert observed(store)['state'] == 'unknown'
    assert store.observe(intent)['state'] == 'completed-foreground'
    store.close()

    store = create(root, 'input-checks')
    for operations in ([], [intent, intent], [intent, replace(other, attempt='d'*32)],
                       [intent, replace(other, boot='00000000-0000-0000-0000-000000000002')],
                       [intent, replace(other, module_sha256='d'*64)], [intent]*129,
                       [m.Expected('../escape', intent.attempt, intent.operation, intent.action_sha256, intent.module_sha256)],
                       [m.Expected(intent.boot, intent.attempt, '../escape', intent.action_sha256, intent.module_sha256)]):
        assert observed(store, operations)['state'] == 'unknown'
    for pins in ((True, *store.identity[1:]), store.identity[:2], (*store.identity[:3], store.identity[3]+1)):
        assert observed(store, pins=pins)['state'] == 'unknown'
    assert observed(store, boot_reader=lambda: 'different boot')['state'] == 'unknown'
    calls = [0]
    def changed_boot():
        calls[0] += 1
        return intent.boot if calls[0] == 1 else '00000000-0000-0000-0000-000000000002'
    assert observed(store, boot_reader=changed_boot)['state'] == 'unknown'
    assert calls[0] == 2
    def failed_reader():
        raise TimeoutError('unknown boot observation')
    assert observed(store, boot_reader=failed_reader)['state'] == 'unknown'
    calls = [0]
    def interrupted_reader():
        calls[0] += 1
        if calls[0] == 2:
            raise KeyboardInterrupt('test-only observation interruption')
        return intent.boot
    try:
        observed(store, boot_reader=interrupted_reader)
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError('observation interrupt swallowed')
    assert observed(store)['state'] == 'receipts-observed'  # Own lease/fds were closed.
    store.close()

    # The observer actually holds the cooperating exclusive lease while reading.
    store = create(root, 'lease-through-snapshot')
    calls = [0]
    def concurrent_claim():
        calls[0] += 1
        if calls[0] == 2:
            try:
                fd = store._lock()
            except BlockingIOError:
                pass
            else:
                os.close(fd)
                raise AssertionError('observer did not retain its lease')
        return intent.boot
    assert observed(store, boot_reader=concurrent_claim)['state'] == 'receipts-observed'
    store.close()

    for mutation in ('orphan', 'unknown-operation', 'native-stage', 'reference-stage',
                     'bad-claim', 'bad-owner', 'symlink', 'fifo', 'permissions', 'hardlink',
                     'oversize', 'bad-base64', 'bad-hash', 'duplicate-key', 'schema', 'not-regular-lease'):
        store = create(root, 'bad-'+mutation)
        claim = store.path/('claim-'+intent.operation+'.json')
        path = store.path/('done-'+intent.operation+'.json')
        if mutation == 'orphan':
            claim.unlink()
        elif mutation == 'unknown-operation':
            write(store.path/('claim-'+other.operation+'.json'), canonical(dict(schema=1, intent=asdict(other))))
        elif mutation in ('native-stage', 'reference-stage'):
            write(store.path/(('native-stage-' if mutation == 'native-stage' else 'stage-')+'f'*32+'.json'), b'partial')
        elif mutation == 'bad-claim':
            claim.write_bytes(canonical(dict(schema=1, intent=asdict(replace(intent, action_sha256='d'*64)))))
        elif mutation == 'bad-owner':
            data = json.loads((store.path/'owner.json').read_text()); data['schema'] = True
            (store.path/'owner.json').write_bytes(canonical(data))
        elif mutation == 'symlink':
            path.unlink(); path.symlink_to(root/'absent-target')
        elif mutation == 'fifo':
            path.unlink(); os.mkfifo(path, 0o600)
        elif mutation == 'permissions':
            path.chmod(0o644)
        elif mutation == 'hardlink':
            os.link(path, root/'outside-link')
        elif mutation == 'oversize':
            path.write_bytes(b'x'*190001)
        elif mutation == 'duplicate-key':
            path.write_bytes(b'{"schema":2,"schema":2}')
        elif mutation == 'not-regular-lease':
            (store.path/'lease.lock').unlink(); os.mkfifo(store.path/'lease.lock', 0o600)
        else:
            data = json.loads(path.read_text())
            if mutation == 'bad-base64': data['stdout_b64'] = '!!'
            if mutation == 'bad-hash': data['stderr_sha256'] = '0'*64
            if mutation == 'schema': data['schema'] = 3
            path.write_bytes(canonical(data))
        assert observed(store)['state'] == 'unknown'
        store.close()

    # A callback simulates a writer ignoring the advisory lease. Final checks
    # reject observed metadata/path changes and discard all recovered outputs.
    for mutation in ('replace-receipt', 'rewrite-receipt', 'replace-root', 'replace-lease', 'new-entry'):
        store = create(root, 'race-'+mutation)
        calls = [0]
        def racing_reader():
            calls[0] += 1
            if calls[0] == 2:
                path = store.path/('done-'+intent.operation+'.json')
                if mutation == 'replace-receipt':
                    raw = path.read_bytes(); path.unlink(); write(path, raw)
                elif mutation == 'rewrite-receipt':
                    path.write_bytes(path.read_bytes()+b' ')
                elif mutation == 'replace-root':
                    store.path.rename(root/'moved-root'); store.path.mkdir(mode=0o700)
                elif mutation == 'replace-lease':
                    (store.path/'lease.lock').rename(store.path/'old-lease')
                    write(store.path/'lease.lock', b'')
                elif mutation == 'new-entry':
                    write(store.path/'unexpected', b'')
            return intent.boot
        assert observed(store, boot_reader=racing_reader)['state'] == 'unknown'
        store.close()

    store = ReceiptStore.create(root/'no-bootstrap')
    before = snapshot(store.path)
    assert observed(store)['state'] == 'unknown'
    assert snapshot(store.path) == before
    store.close()

print('PASS explicit v2 observer: pinned boot/session/inodes, held lease, bounded canonical catalogue, race/staging/legacy rejection, observation-only decisions')
