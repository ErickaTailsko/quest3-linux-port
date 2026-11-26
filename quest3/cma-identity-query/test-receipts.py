#!/usr/bin/env python3
"""Real host file/lock/crash tests; no remote action, ADB or module operation."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile

import receipt_store as m


intent = m.Intent(boot='00000000-0000-0000-0000-000000000001', attempt='a'*32,
                  operation='1'*32, action_sha256=hashlib.sha256(b'fixture-action').hexdigest(),
                  module_sha256='b'*64)
next_intent = replace(intent, operation='2'*32)


def denied(function, *args):
    try:
        function(*args)
    except (m.Blocked, OSError, ValueError, TypeError):
        pass
    else:
        raise AssertionError('unsafe admission accepted')


def observed(store, item=intent):
    value = store.observe(item)
    assert all(value[key] is False for key in ('safe_to_mutate', 'automatic_resume_allowed',
               'tree_quiescence_proven', 'ownership_acquired', 'boot_ready'))
    return value


def wait_byte(fd):
    ready, _, _ = select.select([fd], [], [], 5)
    assert ready and os.read(fd, 1) == b'R', 'fixture child did not become ready'


with tempfile.TemporaryDirectory(prefix='cma-receipt-', dir='/tmp/opencode') as temporary:
    root = Path(temporary)
    store = m.ReceiptStore.create(root/'complete')
    assert observed(store)['state'] == 'not-claimed-observation-only'
    identity = store.identity
    with store.claim(intent) as ticket:
        contender = m.ReceiptStore(store.path, identity)
        try:
            assert observed(contender)['state'] == 'lease-held'
            denied(contender.claim, next_intent)
        finally:
            contender.close()
        # This one action is actually waited/reaped on the host before recording.
        outcome = subprocess.run([sys.executable, '-c', 'print("fixture output")'],
                                 capture_output=True, timeout=5)
        ticket.complete(outcome.returncode, outcome.stdout)
        denied(ticket.complete, 0, b'duplicate')
        assert observed(store)['state'] == 'lease-held'  # Receipt alone != released lease.
    store.close()
    reopened = m.ReceiptStore(root/'complete', identity)
    result = observed(reopened)
    assert result['state'] == 'completed-foreground' and result['receipt_recovered']
    assert result['returncode'] == 0 and result['stdout'] == b'fixture output\n'
    before = {p.name: p.read_bytes() for p in reopened.path.iterdir()}
    denied(reopened.claim, intent)  # Completed operations cannot be replayed either.
    assert before == {p.name: p.read_bytes() for p in reopened.path.iterdir()}
    denied(reopened.claim, replace(intent, operation='3'*32, attempt='c'*32))
    assert observed(reopened, replace(intent, boot='00000000-0000-0000-0000-000000000002'))['state'] == 'unknown'
    assert observed(reopened, replace(intent, action_sha256='c'*64))['state'] == 'unknown'
    assert observed(reopened, replace(intent, module_sha256='c'*64))['state'] == 'unknown'
    with reopened.claim(next_intent) as ticket:
        ticket.complete(23, b'known failure')
    assert observed(reopened, next_intent)['returncode'] == 23
    reopened.close()

    store = m.ReceiptStore.create(root/'invalid-outcome')
    with store.claim(intent) as ticket:
        denied(ticket.complete, 0, b'x'*(m.MAX_STDOUT+1))
        denied(ticket.complete, 0, b'truncated substitute')
    assert observed(store)['state'] == 'claim-without-receipt'
    denied(store.claim, next_intent)
    store.close()

    # Free OS lock after abrupt supervisor death does NOT authorize another op.
    store = m.ReceiptStore.create(root/'crashed')
    identity = store.identity
    store.close()
    pid = os.fork()
    if pid == 0:
        try:
            crashed = m.ReceiptStore(root/'crashed', identity)
            ticket = crashed.claim(intent)
            os._exit(17)  # No finally/close/receipt, as with process death.
        except BaseException:
            os._exit(99)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 17
    store = m.ReceiptStore(root/'crashed', identity)
    assert observed(store)['state'] == 'claim-without-receipt'
    assert observed(store, next_intent)['state'] == 'other-claim-without-receipt'
    denied(store.claim, intent)
    denied(store.claim, next_intent)  # New command nonce cannot bypass the claim.
    denied(store.claim, replace(next_intent, attempt='c'*32))
    store.close()

    # Closing the supervisor's reference must not LOCK_UN the child's shared FD.
    # There are no sleeps/poll loops: pipes establish child lifetime precisely.
    store = m.ReceiptStore.create(root/'inherited-lock')
    ticket = store.claim(intent)
    ready_r, ready_w = os.pipe()
    release_r, release_w = os.pipe()
    code = ('import os; os.write(int(__import__("sys").argv[1]), b"R"); '
            'os.read(int(__import__("sys").argv[2]), 1)')
    child = subprocess.Popen([sys.executable, '-c', code, str(ready_w), str(release_r)],
                             pass_fds=(ticket.fd, ready_w, release_r))
    os.close(ready_w); os.close(release_r)
    try:
        wait_byte(ready_r)
        ticket.complete(0, b'foreground result recorded; child still holds lease')
        ticket.close()
        assert observed(store)['state'] == 'lease-held'
        denied(store.claim, next_intent)
    finally:
        os.write(release_w, b'X'); os.close(release_w); os.close(ready_r)
        child.wait(timeout=5)
    assert observed(store)['state'] == 'completed-foreground'
    store.close()

    # If a lease-owning child survives without any receipt, closing the parent
    # reference first yields held, then unknown after the child exits, never done.
    store = m.ReceiptStore.create(root/'inherited-unfinished')
    ticket = store.claim(intent)
    ready_r, ready_w = os.pipe(); release_r, release_w = os.pipe()
    child = subprocess.Popen([sys.executable, '-c', code, str(ready_w), str(release_r)],
                             pass_fds=(ticket.fd, ready_w, release_r))
    os.close(ready_w); os.close(release_r)
    try:
        wait_byte(ready_r); ticket.close()
        assert observed(store)['state'] == 'lease-held'
    finally:
        os.write(release_w, b'X'); os.close(release_w); os.close(ready_r)
        child.wait(timeout=5)
    assert observed(store)['state'] == 'claim-without-receipt'
    denied(store.claim, next_intent)
    store.close()

    # Publication/durability failures retain the incomplete publication and latch
    # the current object. Reopening never converts an incomplete claim into done.
    for failpoint in ('write', 'file-fsync', 'link', 'directory-fsync', 'unlink'):
        store = m.ReceiptStore.create(root/('failure-'+failpoint))
        identity = store.identity
        ticket = store.claim(intent)
        originals = {name: getattr(m.os, name) for name in ('write', 'fsync', 'link', 'unlink')}
        failed = [False]

        def inject(name):
            def call(*args, **kwargs):
                should = (failpoint == name or
                          name == 'fsync' and failpoint == 'file-fsync' and args[0] != store.fd or
                          name == 'fsync' and failpoint == 'directory-fsync' and args[0] == store.fd)
                if should and not failed[0]:
                    failed[0] = True
                    raise OSError('injected '+failpoint)
                return originals[name](*args, **kwargs)
            return call

        try:
            for name in originals:
                setattr(m.os, name, inject(name))
            denied(ticket.complete, 0, b'outcome')
        finally:
            for name, function in originals.items():
                setattr(m.os, name, function)
            ticket.close(); store.close()
        assert failed[0]
        reopened = m.ReceiptStore(root/('failure-'+failpoint), identity)
        assert observed(reopened)['state'] != 'completed-foreground'
        denied(reopened.claim, next_intent)
        reopened.close()

    # A failed durable claim must never return a ticket to a would-be dispatcher.
    store = m.ReceiptStore.create(root/'failed-claim')
    with store.claim(intent) as ticket:
        ticket.complete(0, b'previous operation')
    identity = store.identity
    original_fsync = m.os.fsync
    try:
        def fail_claim_fsync(fd):
            raise OSError('claim not durable')
        m.os.fsync = fail_claim_fsync
        denied(store.claim, next_intent)
    finally:
        m.os.fsync = original_fsync
        store.close()
    reopened = m.ReceiptStore(root/'failed-claim', identity)
    assert observed(reopened, next_intent)['state'] == 'unknown'
    denied(reopened.claim, replace(intent, operation='3'*32))
    reopened.close()

    # Untrusted/partial metadata never authorizes recovery/admission.
    for mutation in ('bad-hash', 'foreign-intent', 'duplicate-json', 'truncated',
                     'symlink', 'mode', 'extra-link', 'orphan', 'oversized', 'stage'):
        store = m.ReceiptStore.create(root/('corrupt-'+mutation))
        with store.claim(intent) as ticket:
            ticket.complete(0, b'data')
        path = store.path/('done-'+intent.operation+'.json')
        data = json.loads(path.read_text())
        if mutation == 'bad-hash':
            data['stdout_sha256'] = '0'*64; path.write_text(json.dumps(data))
        elif mutation == 'foreign-intent':
            data['intent']['action_sha256'] = 'c'*64; path.write_text(json.dumps(data))
        elif mutation == 'duplicate-json':
            path.write_text('{"schema":1,"schema":1}')
        elif mutation == 'truncated':
            path.write_bytes(path.read_bytes()[:-5])
        elif mutation == 'symlink':
            path.unlink(); path.symlink_to('/does-not-exist')
        elif mutation == 'mode':
            path.chmod(0o644)
        elif mutation == 'extra-link':
            os.link(path, root/'extra-link')
        elif mutation == 'orphan':
            (store.path/('claim-'+intent.operation+'.json')).unlink()
        elif mutation == 'oversized':
            path.write_bytes(b'x'*(m.MAX_JSON+1))
        elif mutation == 'stage':
            (store.path/('stage-'+'f'*32+'.json')).write_bytes(b'partial')
        assert observed(store)['state'] == 'unknown'
        denied(store.claim, next_intent)
        store.close()

    store = m.ReceiptStore.create(root/'path-pin')
    identity = store.identity
    denied(m.ReceiptStore, store.path, (identity[0], identity[1]+1, *identity[2:]))
    denied(m.ReceiptStore, store.path, ('not-dev', *identity[1:]))
    store.path.rename(root/'moved-path-pin')
    store.path.mkdir(mode=0o700)
    denied(store.observe, intent)
    store.close()

    store = m.ReceiptStore.create(root/'lease-pin')
    with store.claim(intent) as ticket:
        ticket.complete(0, b'recorded')
        (store.path/'lease.lock').rename(store.path/'old-lease.lock')
        (store.path/'lease.lock').touch(mode=0o600)
        denied(store.observe, intent)  # New lock inode cannot stand in for held old lease.
        denied(store.claim, next_intent)
    store.close()

print('PASS host receipt store: durable immutable claims/receipts, held leases, crash barriers, inherited FDs, no replay/cleanup authorization')
