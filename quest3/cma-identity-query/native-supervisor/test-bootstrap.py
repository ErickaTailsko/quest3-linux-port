#!/usr/bin/env python3
"""Native metadata bootstrap in private host fixtures only; no device/activation."""
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile

import bootstrap_receipt as b

folder = Path(__file__).resolve().parent
sys.path.insert(0, str(folder.parent))
from receipt_store import Intent, ReceiptStore, Blocked


def denied(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except (ValueError, Blocked):
        pass
    else:
        raise AssertionError('unsafe bootstrap/metadata transition accepted')


def ready(channel):
    readable, _, _ = select.select([channel], [], [], 5)
    assert readable and channel.recv(2) == b'R\n'


def snapshot(path):
    if not path.exists(): return None
    return {p.name:(p.lstat().st_mode,p.lstat().st_ino,p.read_bytes() if p.is_file() and not p.is_symlink() else b'NONREG')
            for p in path.iterdir()}


def safe(value):
    for key in ('pin_import_permitted','local_pin_ack_verified','authorization_verified','bootstrap_verified',
                'original_response_verified','publication_durability_verified','execution_enabled',
                'admission_enabled','safe_to_mutate','replay_permitted','cleanup_permitted','automatic_resume_allowed'):
        assert value[key] is False
    return value


with tempfile.TemporaryDirectory(prefix='q3-bootstrap-', dir='/tmp/opencode') as temporary:
    root = Path(temporary)
    cc = os.environ.get('CC','cc')
    flags = ['-std=c11','-O2','-Wall','-Wextra','-Werror','-flto','-fstack-protector-strong',
             '-D_FORTIFY_SOURCE=2','-fPIE','-pie','-Wl,-z,relro,-z,now']
    disabled, worker = root/'bootstrap-disarmed', root/'bootstrap-host-test'
    for target, extra in ((disabled,[]),(worker,['-DQ3_BOOTSTRAP_HOST_TEST'])):
        subprocess.run([cc,*flags,*extra,str(folder/'bootstrap.c'),'-o',str(target)],check=True,timeout=60)
    result = subprocess.run([str(disabled),'--host-bootstrap'],capture_output=True,timeout=5)
    assert result.returncode == 77 and b'Disarmed' in result.stderr and not result.stdout

    def parent(name):
        path = root/name; path.mkdir(mode=0o700)
        fd = os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        info = os.fstat(fd)
        return path,fd,(info.st_dev,info.st_ino)

    def request(pins, *, attempt='a'*32, operation='1'*32, boot='00000000-0000-0000-0000-000000000001'):
        return b.canonical(dict(schema=1,profile=b.PROFILE,execution_enabled=False,attempt=attempt,
               authorization_sha256='c'*64,boot=boot,bootstrap_operation=operation,device_binding_sha256='d'*64,
               helper_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),local_intent_sha256='e'*64,
               module_sha256='b'*64,parent_dev=pins[0],parent_ino=pins[1]))

    def start(path,fd,pins,raw,*,fault=None,pause=None,bad_hash=False,wrong_pin=False):
        req = b.parse_request(raw)
        left,right = socket.socketpair() if pause else (None,None)
        control = right.fileno() if right else -1
        args = [str(worker),'--host-bootstrap',str(path),str(fd),str(pins[0]),str(pins[1]+int(wrong_pin)),
                req['boot'],req['attempt'],req['bootstrap_operation'],req['device_binding_sha256'],
                req['helper_sha256'],req['module_sha256'],req['authorization_sha256'],req['local_intent_sha256'],
                '0'*64 if bad_hash else b.request_commitment(raw),str(control)]
        env = {**os.environ}
        for key in ('Q3_BOOTSTRAP_FAULT','Q3_BOOTSTRAP_PAUSE'): env.pop(key,None)
        if fault: env['Q3_BOOTSTRAP_FAULT']=fault
        if pause: env['Q3_BOOTSTRAP_PAUSE']=pause
        try:
            process = subprocess.Popen(args,pass_fds=(fd,control) if right else (fd,),
                                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        finally:
            if right:right.close()
        return process,left

    def observed(path,pins,raw,reader=None):
        req = b.parse_request(raw)
        value = safe(b.observe(path,pins,raw,boot_reader=reader or (lambda:req['boot'])))
        if value['state'] != 'metadata-observed-no-activation':
            assert value['candidate_pins'] is None and not value['metadata_matches_request']
        return value

    path,fd,pins = parent('success'); raw = request(pins)
    assert observed(path,pins,raw)['state'] == 'root-not-observed'
    assert not (path/b.ROOT_NAME).exists()
    process,_ = start(path,fd,pins,raw)
    stdout,stderr = process.communicate(timeout=5)
    assert process.returncode == 0 and not stderr
    metadata = observed(path,pins,raw)
    assert metadata['state'] == 'metadata-observed-no-activation'
    registry = path/b.ROOT_NAME
    before = snapshot(registry)
    receipt_raw = (registry/'bootstrap-receipt.json').read_bytes()
    parsed = safe(b.parse_receipt(receipt_raw,raw))
    assert parsed == metadata
    assert b.reply_matches(stdout,raw,metadata['receipt_sha256'])
    for _ in range(5): assert observed(path,pins,raw) == metadata
    assert snapshot(registry) == before
    # Existing metadata is a persistent barrier even after the creator exited.
    for another in (raw,request(pins,attempt='f'*32,operation='2'*32),
                    request(pins,boot='00000000-0000-0000-0000-000000000002')):
        retry,_ = start(path,fd,pins,another); out,_ = retry.communicate(timeout=5)
        assert retry.returncode == 77 and not out and snapshot(registry) == before
    # Proposed pins cannot cause the v1 writer to admit an action implicitly.
    legacy = ReceiptStore(registry,metadata['candidate_pins'])
    legacy_intent = Intent(b.parse_request(raw)['boot'],'a'*32,'3'*32,'c'*64,'b'*64)
    assert legacy.observe(legacy_intent)['state'] == 'unknown'
    denied(legacy.claim,legacy_intent)
    assert snapshot(registry) == before
    legacy.close()
    for reply in (b'',stdout[:-1],stdout+b'\n',stdout.replace(b'1'*32,b'2'*32)):
        denied(b.reply_matches,reply,raw,metadata['receipt_sha256'])
    denied(b.parse_receipt,receipt_raw,request(pins,attempt='f'*32,operation='2'*32))
    bad = json.loads(receipt_raw);bad['local_pin_ack_verified']=True
    denied(b.parse_receipt,b.canonical(bad),raw)
    bad = json.loads(receipt_raw);bad['root_ino']=True
    denied(b.parse_receipt,b.canonical(bad),raw)
    denied(b.parse_request,raw+b'\n')
    duplicate = raw.replace(b'"schema":1',b'"schema":1,"schema":1')
    denied(b.parse_request,duplicate)
    os.close(fd)

    for name,kwargs in (('bad-hash',dict(bad_hash=True)),('wrong-pin',dict(wrong_pin=True))):
        path,fd,pins = parent(name);raw = request(pins)
        process,_ = start(path,fd,pins,raw,**kwargs);process.communicate(timeout=5)
        assert process.returncode == 77 and not (path/b.ROOT_NAME).exists()
        os.close(fd)
    for kind in ('empty','file','symlink'):
        path,fd,pins = parent('preexisting-'+kind);raw = request(pins)
        if kind=='empty': (path/b.ROOT_NAME).mkdir(mode=0o700)
        if kind=='file': (path/b.ROOT_NAME).write_bytes(b'unowned')
        if kind=='symlink': (path/b.ROOT_NAME).symlink_to(root/'absent')
        info = (path/b.ROOT_NAME).lstat()
        process,_ = start(path,fd,pins,raw);out,_ = process.communicate(timeout=5)
        assert process.returncode == 77 and not out and (path/b.ROOT_NAME).lstat().st_ino == info.st_ino
        os.close(fd)

    for stage in ('after-mkdir','after-lease','intent-file-fsync','intent-link','intent-directory-fsync',
                  'intent-unlink','intent-final-fsync','receipt-file-fsync','receipt-link',
                  'receipt-directory-fsync','receipt-unlink','receipt-final-fsync','before-reply'):
        path,fd,pins = parent('fault-'+stage);raw = request(pins)
        process,_ = start(path,fd,pins,raw,fault=stage);out,_ = process.communicate(timeout=5)
        assert process.returncode == 74 and not out and (path/b.ROOT_NAME).is_dir()
        value = observed(path,pins,raw)
        if stage in ('receipt-final-fsync','before-reply'):
            assert value['state'] == 'metadata-observed-no-activation'
            assert not value['publication_durability_verified'] and not value['pin_import_permitted']
        else: assert value['state'] == 'unknown'
        before = snapshot(path/b.ROOT_NAME)
        retry,_ = start(path,fd,pins,raw);retry.communicate(timeout=5)
        assert retry.returncode == 77 and snapshot(path/b.ROOT_NAME) == before
        os.close(fd)

    # Concurrent creator/new nonce is rejected, not queued for takeover.
    path,fd,pins = parent('concurrent');raw = request(pins)
    first,channel = start(path,fd,pins,raw,pause='after-lease');ready(channel)
    assert observed(path,pins,raw)['state'] == 'lease-held'
    second,_ = start(path,fd,pins,request(pins,attempt='f'*32,operation='2'*32))
    out,_ = second.communicate(timeout=5);assert second.returncode == 77 and not out
    channel.sendall(b'X');channel.close();first.communicate(timeout=5)
    assert first.returncode == 0 and observed(path,pins,raw)['state'] == 'metadata-observed-no-activation'
    os.close(fd)

    # Supervisor death leaves partial root/lease; OS unlock is not permission to recreate.
    path,fd,pins = parent('killed');raw = request(pins)
    process,channel = start(path,fd,pins,raw,pause='after-lease');ready(channel)
    process.kill();process.wait(timeout=5);channel.close()
    process.stdout.close();process.stderr.close()
    assert observed(path,pins,raw)['state'] == 'unknown'
    before = snapshot(path/b.ROOT_NAME)
    retry,_ = start(path,fd,pins,raw);retry.communicate(timeout=5)
    assert retry.returncode == 77 and snapshot(path/b.ROOT_NAME) == before
    os.close(fd)

    # Replacements during bootstrap fail closed; no metadata enters the new
    # root/lease and abandoned evidence is not removed by the creator.
    for target in ('parent','root','lease'):
        path,fd,pins = parent('creation-race-'+target);raw = request(pins)
        stage = 'after-mkdir' if target=='root' else 'after-lease'
        process,channel = start(path,fd,pins,raw,pause=stage);ready(channel)
        if target=='parent':
            retained = root/'creation-parent-retained'
            path.rename(retained);path.mkdir(mode=0o700)
        elif target=='root':
            retained = path/'retained-root'
            (path/b.ROOT_NAME).rename(retained)
            (path/b.ROOT_NAME).mkdir(mode=0o700)
        else:
            retained = path/b.ROOT_NAME
            lease_path = retained/'lease.lock'
            lease_path.rename(retained/'retained-lease')
            replacement = os.open(lease_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            os.close(replacement)
        channel.sendall(b'X');channel.close()
        out,_ = process.communicate(timeout=5)
        assert process.returncode==74 and not out
        assert retained.exists()
        assert not list(path.rglob('bootstrap-intent.json'))
        assert not list(retained.rglob('bootstrap-intent.json'))
        os.close(fd)

    # Response loss after durable metadata cannot trigger an overwrite/retry.
    path,fd,pins = parent('lost-reply');raw = request(pins)
    process,channel = start(path,fd,pins,raw,pause='before-reply');ready(channel)
    process.stdout.close();channel.sendall(b'X');channel.close()
    process.wait(timeout=5);assert process.returncode == 74
    assert observed(path,pins,raw)['state'] == 'metadata-observed-no-activation'
    process.stderr.close();os.close(fd)

    # Invalid filesystem objects/catalogues cannot be promoted to pin proposals.
    for target in ('extra','intent-symlink','receipt-hardlink','lease-mode','root-mode'):
        path,fd,pins = parent('invalid-object-'+target);raw = request(pins)
        process,_ = start(path,fd,pins,raw);process.communicate(timeout=5)
        assert process.returncode==0
        registry = path/b.ROOT_NAME
        if target=='extra': (registry/'unexpected').write_bytes(b'foreign')
        if target=='intent-symlink':
            intent = registry/'bootstrap-intent.json'
            intent.rename(path/'retained-intent');intent.symlink_to(path/'retained-intent')
        if target=='receipt-hardlink': os.link(registry/'bootstrap-receipt.json',path/'receipt-alias')
        if target=='lease-mode': (registry/'lease.lock').chmod(0o644)
        if target=='root-mode': registry.chmod(0o755)
        assert observed(path,pins,raw)['state']=='unknown'
        os.close(fd)

    # Observed parent/root replacement never activates or imports new identities.
    for target in ('parent','root','receipt','boot'):
        path,fd,pins = parent('observation-race-'+target);raw = request(pins)
        process,_ = start(path,fd,pins,raw);process.communicate(timeout=5);assert process.returncode==0
        calls=[0]
        def raced_boot():
            calls[0]+=1
            if calls[0]==2:
                if target=='parent': path.rename(root/('moved-'+target));path.mkdir(mode=0o700)
                if target=='root': (path/b.ROOT_NAME).rename(path/'moved-registry');(path/b.ROOT_NAME).mkdir(mode=0o700)
                if target=='receipt':
                    file=path/b.ROOT_NAME/'bootstrap-receipt.json';file.write_bytes(file.read_bytes()+b' ')
                if target=='boot': return '00000000-0000-0000-0000-000000000002'
            return b.parse_request(raw)['boot']
        assert observed(path,pins,raw,raced_boot)['state']=='unknown'
        os.close(fd)

source=(folder/'bootstrap.c').read_text()
for forbidden in ('execve(', 'fork(', 'system(', 'popen(', 'finit_module(', 'delete_module(', 'reboot(', 'rmdir('):
    assert forbidden not in source
assert 'LOCK_UN)' not in source
print('PASS native bootstrap host reference: exclusive canonical root, parent/lease pins, no takeover, durable metadata faults, concurrent/SIGKILL/lost reply; no activation/device action')
