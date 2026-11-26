#!/usr/bin/env python3
"""Compile/run native host fixtures only; no Android, ADB, shell action or module."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import tempfile

folder = Path(__file__).resolve().parent
source = (folder/'supervisor.c').read_text()
for forbidden in ('finit_module(', 'init_module(', 'delete_module(', 'reboot(',
                  'system(', 'popen(', 'execl(', 'LOCK_UN'):
    assert forbidden not in source
sys.path.insert(0, str(folder.parent))
from receipt_store import ReceiptStore, Intent
from native_receipt import parse
from v2_catalog import observe as observe_v2


FIXTURE = r'''
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static void emit(int fd,const void *data,size_t size) {
    const char *p=data;
    while(size) { ssize_t n=write(fd,p,size); if(n<0 && errno==EINTR) continue; if(n<=0) _exit(90); p+=n;size-=(size_t)n; }
}
int main(int argc,char **argv) {
    if(argc!=3) return 99;
    const char *mode=argv[1];int control=atoi(argv[2]);
    if(!strcmp(mode,"block") || !strcmp(mode,"close-streams")) {
        char c;char ready[64];int n=snprintf(ready,sizeof(ready),"R%ld\n",(long)getpid());
        if(!strcmp(mode,"close-streams")) { close(1);close(2); }
        emit(control,ready,(size_t)n);
        if(read(control,&c,1)!=1) return 98;
        if(!strcmp(mode,"block")) emit(1,"released\n",9);
        return 0;
    }
    if(!strcmp(mode,"signal")) { raise(SIGTERM);return 97; }
    if(!strcmp(mode,"overflow")) { char data[4096]={0}; for(int i=0;i<17;i++) emit(1,data,sizeof(data)); return 0; }
    if(!strcmp(mode,"binary")) { unsigned char data[256];for(int i=0;i<256;i++)data[i]=(unsigned char)i;emit(1,data,sizeof(data));return 0; }
    if(!strcmp(mode,"fd-clean")) {
        DIR *d=opendir("/proc/self/fd");struct dirent *e;int extra=0;
        if(!d)return 96;
        while((e=readdir(d))) { char *end;long fd=strtol(e->d_name,&end,10);if(!*end && fd>2 && fd!=dirfd(d)) extra++; }
        closedir(d);return extra==1 ? 0 : 95; /* only the inherited lease */
    }
    emit(1,"fixture\n",8);emit(2,"diagnostic\n",11);
    return !strcmp(mode,"fail") ? 23 : !strcmp(mode,"exit-last") ? 127 : 0;
}
'''


def line(sock):
    data = b''
    while not data.endswith(b'\n'):
        ready, _, _ = select.select([sock], [], [], 5)
        assert ready, 'fixture synchronization timeout'
        value = sock.recv(1)
        assert value, 'fixture synchronization EOF'
        data += value
        assert len(data) < 64
    return data


def denied(function, *args):
    try:
        function(*args)
    except (ValueError, TypeError):
        pass
    else:
        raise AssertionError('invalid native receipt accepted')


with tempfile.TemporaryDirectory(prefix='cma-native-', dir='/tmp/opencode') as temporary:
    root = Path(temporary)
    cc = os.environ.get('CC', 'cc')
    flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-flto',
             '-fstack-protector-strong', '-D_FORTIFY_SOURCE=2', '-fPIE', '-pie', '-Wl,-z,relro,-z,now']
    disarmed, supervisor, fixture = root/'disarmed', root/'supervisor', root/'fixture'
    for target, extra in ((disarmed, []), (supervisor, ['-DQ3_SUPERVISOR_HOST_TEST'])):
        subprocess.run([cc, *flags, *extra, str(folder/'supervisor.c'), '-o', str(target)], check=True, timeout=60)
    result = subprocess.run([str(disarmed), '--host-fixture'], capture_output=True, timeout=5)
    assert result.returncode == 77 and b'Disarmed' in result.stderr
    (root/'fixture.c').write_text(FIXTURE)
    subprocess.run([cc, *flags, str(root/'fixture.c'), '-o', str(fixture)], check=True, timeout=60)

    # Cross-check all SHA block/padding boundaries and larger binary payloads.
    (root/'hash.c').write_text('#include <stdio.h>\n#include "sha256.h"\n'
                             'int main(void){unsigned char data[100000];char h[65];'
                             'size_t n=fread(data,1,sizeof(data),stdin);sha256_hex(data,n,h);puts(h);return 0;}\n')
    subprocess.run([cc, *flags, '-I'+str(folder), str(root/'hash.c'), '-o', str(root/'hash')], check=True, timeout=60)
    for size in (0, 1, 3, 55, 56, 63, 64, 65, 119, 120, 127, 128, 65536):
        data = bytes((i*37+11) % 256 for i in range(size))
        checked = subprocess.run([str(root/'hash')], input=data, capture_output=True, timeout=5, check=True)
        assert checked.stdout.strip().decode() == hashlib.sha256(data).hexdigest()

    def start(name, mode='ok', *, change_action=False, corrupt=False, executable=fixture, control=False, fault=None):
        store = ReceiptStore.create(root/name)
        digest = hashlib.sha256(executable.read_bytes()).digest()
        action = hashlib.sha256(b'host-fixture-v1\0'+mode.encode()+b'\0'+digest).hexdigest()
        intent = Intent('00000000-0000-0000-0000-000000000001','a'*32,'1'*32,action,'b'*64)
        ticket = store.claim(intent)
        fd = os.open(executable, os.O_RDONLY | os.O_NOFOLLOW)
        left, right = socket.socketpair() if control else (None, None)
        control_fd = right.fileno() if right else -1
        args = [str(supervisor), '--host-fixture', str(store.path), str(store.fd), str(ticket.fd), str(fd),
                *map(str, store.identity), intent.boot, intent.attempt, intent.operation,
                'c'*64 if change_action else intent.action_sha256, intent.module_sha256, mode, str(control_fd)]
        if corrupt:
            (store.path/('claim-'+intent.operation+'.json')).write_text('{}')
        # An unrelated descriptor must not leak into the fixture child.
        secret = os.open(root/'fixture.c', os.O_RDONLY)
        inherited = (store.fd, ticket.fd, fd, secret) + ((control_fd,) if right else ())
        try:
            environment = {**os.environ}
            environment.pop('Q3_NATIVE_FAULT', None)
            if fault:
                environment['Q3_NATIVE_FAULT'] = fault
            process = subprocess.Popen(args, pass_fds=inherited, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        finally:
            ticket.close(); os.close(fd); os.close(secret)
            if right:
                right.close()
        return store, intent, process, left

    def receipt(store, intent):
        raw = (store.path/('done-'+intent.operation+'.json')).read_bytes()
        result = parse(raw, intent)
        assert all(result[key] is False for key in ('safe_to_mutate', 'automatic_resume_allowed',
                   'tree_quiescence_proven', 'lease_free_verified', 'boot_ready'))
        # Native schema v2 must NOT silently pass the reference schema-v1 ledger.
        assert store.observe(intent)['state'] == 'unknown'
        observed = observe_v2(store.path, store.identity, [intent], boot_reader=lambda: intent.boot)
        assert observed['state'] == 'receipts-observed' and observed['catalog_verified']
        assert observed['receipts'][intent.operation]['result'] == result
        assert not observed['sequence_verified'] and not observed['safe_to_mutate']
        assert not observed['replay_permitted'] and not observed['cleanup_permitted']
        return raw, result

    for mode, expected in (('ok', 0), ('fail', 23), ('exit-last', 127), ('binary', 0), ('fd-clean', 0), ('signal', 15)):
        store, intent, process, _ = start(mode, mode)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0 and not stderr, (mode, process.returncode, stderr)
        assert stdout == b'ERIS_NATIVE_RECEIPT '+intent.operation.encode()+b'\n'
        raw, value = receipt(store, intent)
        assert value['termination_value'] == expected and value['exec_errno'] == 0
        assert value['termination_kind'] == ('signal' if mode == 'signal' else 'exit')
        if mode == 'ok':
            assert value['stdout'] == b'fixture\n' and value['stderr'] == b'diagnostic\n'
            sample, sample_intent = raw, intent
            # Reopening the same valid claim with a completed native receipt
            # must reject BEFORE executing the fixture a second time.
            lease = os.open(store.path/'lease.lock', os.O_RDWR | os.O_NOFOLLOW)
            executable = os.open(fixture, os.O_RDONLY | os.O_NOFOLLOW)
            retry = list(process.args); retry[4] = str(lease); retry[5] = str(executable)
            try:
                replay = subprocess.run(retry, pass_fds=(store.fd, lease, executable), capture_output=True, timeout=5)
                assert replay.returncode == 77 and not replay.stdout
                assert (store.path/('done-'+intent.operation+'.json')).read_bytes() == raw
            finally:
                os.close(lease); os.close(executable)
        if mode == 'binary':
            assert value['stdout'] == bytes(range(256))
        store.close()

    bad_elf = root/'bad-elf'; bad_elf.write_bytes(b'\x7fELFnot-an-executable'); bad_elf.chmod(0o700)
    store, intent, process, _ = start('exec-error', executable=bad_elf)
    process.communicate(timeout=5)
    assert process.returncode == 0
    _, value = receipt(store, intent)
    assert value['exec_errno'] and value['termination_kind'] == 'exit' and value['termination_value'] == 127
    store.close()

    for fault in ('file-fsync', 'link', 'directory-fsync', 'unlink', 'final-fsync'):
        store, intent, process, _ = start('fault-'+fault, fault=fault)
        stdout, _ = process.communicate(timeout=5)
        assert process.returncode == 74 and not stdout
        # Even if final bytes are visible after a durability error, the worker
        # does not acknowledge successful publication or authorize any retry.
        if fault != 'final-fsync':
            assert store.observe(intent)['state'] == 'unknown'
            assert (store.path/('native-stage-'+intent.operation+'.json')).exists()
            assert observe_v2(store.path, store.identity, [intent], boot_reader=lambda: intent.boot)['state'] == 'unknown'
        else:
            visible = observe_v2(store.path, store.identity, [intent], boot_reader=lambda: intent.boot)
            assert visible['state'] == 'receipts-observed'
            assert not visible['publication_durability_verified'] and not visible['original_response_verified']
            assert not visible['safe_to_mutate'] and not visible['automatic_resume_allowed']
        store.close()

    for mode in ('block', 'close-streams'):
        store, intent, process, channel = start('wait-'+mode, mode, control=True)
        ready = line(channel); assert ready.startswith(b'R')
        assert store.observe(intent)['state'] == 'lease-held'
        assert observe_v2(store.path, store.identity, [intent], boot_reader=lambda: intent.boot)['state'] == 'lease-held'
        assert not (store.path/('done-'+intent.operation+'.json')).exists()
        if mode == 'block':
            process.send_signal(signal.SIGTERM)
            assert line(channel) == b'S\n'  # Handler ran; it did NOT kill/forward to child.
            assert store.observe(intent)['state'] == 'lease-held'
        channel.sendall(b'X'); channel.close()
        process.communicate(timeout=5)
        assert process.returncode == 0
        _, value = receipt(store, intent)
        assert value['termination_kind'] == 'exit' and value['termination_value'] == 0
        assert value['supervisor_interrupted'] == (mode == 'block')
        store.close()

    # Lost client stdout occurs AFTER durable receipt publication, not before.
    store, intent, process, channel = start('lost-response', 'block', control=True)
    assert line(channel).startswith(b'R')
    process.stdout.close()
    channel.sendall(b'X'); channel.close()
    process.wait(timeout=5); assert process.returncode == 74
    assert receipt(store, intent)[1]['stdout'] == b'released\n'
    process.stderr.close(); store.close()

    # SIGKILL of the supervisor cannot release the surviving child's lease.
    store, intent, process, channel = start('killed-supervisor', 'block', control=True)
    child_pid = int(line(channel)[1:])
    pidfd = os.pidfd_open(child_pid)
    try:
        process.kill(); process.wait(timeout=5)
        assert store.observe(intent)['state'] == 'lease-held'
        channel.sendall(b'X'); channel.close()
        exited, _, _ = select.select([pidfd], [], [], 5)
        assert exited, 'fixture child failed to exit'
        assert store.observe(intent)['state'] == 'claim-without-receipt'
        assert observe_v2(store.path, store.identity, [intent], boot_reader=lambda: intent.boot)['state'] == 'claims-unresolved'
    finally:
        # pidfd identifies only the test child, never an unowned/reused PID.
        exited, _, _ = select.select([pidfd], [], [], 0)
        if not exited:
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
        os.close(pidfd)
        process.stdout.close(); process.stderr.close(); store.close()

    store, intent, process, _ = start('overflow', 'overflow')
    process.communicate(timeout=5)
    assert process.returncode == 74 and store.observe(intent)['state'] == 'claim-without-receipt'
    store.close()
    for name, kwargs in (('wrong-action', {'change_action': True}), ('bad-claim', {'corrupt': True})):
        store, intent, process, _ = start(name, **kwargs)
        stdout, _ = process.communicate(timeout=5)
        assert process.returncode == 77 and not stdout
        assert not (store.path/('done-'+intent.operation+'.json')).exists()
        store.close()

    # A publication collision never gets overwritten or acknowledged as done.
    store, intent, process, channel = start('publication-failure', 'block', control=True)
    assert line(channel).startswith(b'R')
    stage = store.path/('native-stage-'+intent.operation+'.json')
    stage.write_bytes(b'preserve-this'); stage.chmod(0o600)
    channel.sendall(b'X'); channel.close(); process.communicate(timeout=5)
    assert process.returncode == 74 and stage.read_bytes() == b'preserve-this'
    assert not (store.path/('done-'+intent.operation+'.json')).exists()
    store.close()

    denied(parse, sample, replace(sample_intent, action_sha256='c'*64))
    denied(parse, sample+b'x', sample_intent)
    denied(parse, b'x'*190000, sample_intent)
    for key, value in (('schema', True), ('tree_quiescence_proven', True), ('safe_to_mutate', True),
                       ('stdout_sha256', '0'*64), ('stderr_size', 0), ('termination_value', True)):
        record = json.loads(sample); record[key] = value
        denied(parse, json.dumps(record).encode(), sample_intent)
    denied(parse, b'{"schema":2,"schema":2}', sample_intent)

print('PASS native host supervisor: wait/reap, inherited lease, signals/SIGKILL, bounded streams, receipt-before-response, disarmed default; no Android/device test')
