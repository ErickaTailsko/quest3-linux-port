#!/usr/bin/env python3
"""Local HOST FIXTURE journal regressions; no device, transport or activation."""
import json
import os
from pathlib import Path
import select
import signal
import socket
import tempfile
from unittest import mock

import bootstrap_ack_reference as a
import bootstrap_receipt as b


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except (a.Frozen,ValueError,OSError): pass
    else: raise AssertionError('unsafe fixture ACK/import transition accepted')


def safe(result):
    for key,value in a.flags().items(): assert result[key] is value is False
    assert 'checkpoint' not in result
    return result


def snapshot(path):
    return {p.name:(p.lstat().st_ino,p.lstat().st_mode,p.read_bytes() if p.is_file() and not p.is_symlink() else None)
            for p in path.iterdir()}


with tempfile.TemporaryDirectory(prefix='q3-pin-ack-',dir='/tmp/opencode') as temporary:
    root=Path(temporary)

    def fixtures(name):
        parent=root/name; parent.mkdir(mode=0o700)
        info=parent.stat(); pins=(info.st_dev,info.st_ino)
        request=b.canonical(dict(schema=1,profile=b.PROFILE,execution_enabled=False,
            boot='00000000-0000-0000-0000-000000000001',attempt='a'*32,bootstrap_operation='1'*32,
            authorization_sha256='b'*64,device_binding_sha256='c'*64,helper_sha256='d'*64,
            local_intent_sha256='e'*64,module_sha256='f'*64,parent_dev=7,parent_ino=101))
        remote_pins=[7,102,7,103]
        receipt=b.canonical(dict(schema=1,profile=b.PROFILE,producer='host-native-bootstrap-reference',
            admission_enabled=False,bootstrap_phase='metadata-only-no-activation',execution_enabled=False,
            local_pin_ack_verified=False,request=b.parse_request(request),request_sha256=b.request_commitment(request),
            root_dev=7,root_ino=102,lease_dev=7,lease_ino=103))
        response=('ERIS_BOOTSTRAP_RECEIPT '+'1'*32+' '+a.digest(receipt)+'\n').encode()
        return parent,pins,request,receipt,response,remote_pins

    def create(fixture,**kwargs): return a.HostAckJournal.create(*fixture[:3],**kwargs)

    def ack(journal,fixture,**kwargs):
        return journal.acknowledge_fixture(*fixture[3:],completion=kwargs.get('completion','host-fixture-complete'))

    def journal_pins(parent):
        path=parent/a.NAME; info=path.stat(); lease=(path/'lease.lock').stat()
        return (info.st_dev,info.st_ino,lease.st_dev,lease.st_ino)

    def observe(fixture,pins):
        return safe(a.observe(fixture[0],fixture[1],pins,fixture[2]))

    fixture=fixtures('success'); journal=create(fixture)
    pins=journal_pins(fixture[0])
    assert observe(fixture,pins)['state']=='lease-held'
    before=snapshot(fixture[0]/a.NAME)
    denied(create,fixture)  # another creator cannot wait for/take over a lease
    assert snapshot(fixture[0]/a.NAME)==before
    checkpoint=ack(journal,fixture)
    assert type(checkpoint) is tuple and len(checkpoint)==6
    assert not (fixture[0]/a.NAME/'import.json').exists()
    result=safe(journal.import_fixture_pins(checkpoint))
    assert result['state']=='fixture-pins-imported-no-activation'
    assert result['imported_fixture_pins']==fixture[5]
    assert set(p.name for p in (fixture[0]/a.NAME).iterdir())=={'lease.lock','intent.json','ack.json','import.json'}
    journal.close()
    before=snapshot(fixture[0]/a.NAME)
    for _ in range(3):
        assert observe(fixture,pins)['state']=='fixture-records-observed-not-recovered'
        assert observe(fixture,pins)['complete_records']==3
    assert snapshot(fixture[0]/a.NAME)==before
    denied(create,fixture)
    denied(journal.import_fixture_pins,checkpoint)

    # Unknown/missing completion or response cannot produce a local ACK.
    for index,change in enumerate(('unknown','lost','truncated','foreign-response','bad-pins','foreign-receipt')):
        fixture=fixtures('bad-evidence-'+str(index)); journal=create(fixture)
        modified=list(fixture)
        completion='host-fixture-complete'
        if change=='unknown': completion='unknown'
        if change=='lost': modified[4]=b''
        if change=='truncated': modified[4]=modified[4][:-1]
        if change=='foreign-response': modified[4]=modified[4].replace(b'1'*32,b'2'*32)
        if change=='bad-pins': modified[5]=[7,102,7,104]
        if change=='foreign-receipt':
            raw=json.loads(modified[3]); raw['request']['attempt']='2'*32; modified[3]=b.canonical(raw)
        denied(ack,journal,modified,completion=completion)
        assert journal.poisoned and not (fixture[0]/a.NAME/'ack.json').exists()
        before=snapshot(fixture[0]/a.NAME)
        denied(ack,journal,fixture)
        denied(journal.import_fixture_pins,())
        assert snapshot(fixture[0]/a.NAME)==before
        pins=journal_pins(fixture[0]); journal.close()
        assert observe(fixture,pins)['complete_records']==1
        denied(create,fixture)

    # A valid on-disk ACK never repairs a missing caller-held live checkpoint.
    for kind in ('none','list','foreign','before-ack','duplicate-ack','duplicate-import'):
        fixture=fixtures('checkpoint-'+kind); journal=create(fixture)
        if kind=='before-ack': denied(journal.import_fixture_pins,())
        else:
            checkpoint=ack(journal,fixture)
            if kind=='duplicate-ack': denied(ack,journal,fixture)
            elif kind=='duplicate-import':
                safe(journal.import_fixture_pins(checkpoint))
                denied(journal.import_fixture_pins,checkpoint)
            else:
                bad=None if kind=='none' else list(checkpoint) if kind=='list' else ('f'*64,*checkpoint[1:])
                denied(journal.import_fixture_pins,bad)
        assert journal.poisoned
        journal.close()
        denied(create,fixture)

    # Preserve every publication failure; final bytes do not prove fsync/ACK.
    for record in ('intent','ack','import'):
        phases=('file-fsync','link','directory-fsync','unlink','final-fsync')
        if record!='intent': phases+=('before-return',)
        for phase in phases:
            fixture=fixtures('fault-'+record+'-'+phase)
            stage=record+'-'+phase
            def fault(point):
                if point==stage: raise OSError('injected '+stage)
            if record=='intent': denied(create,fixture,fault=fault)
            else:
                journal=create(fixture)
                if record=='ack':
                    journal.fault=fault; denied(ack,journal,fixture)
                else:
                    checkpoint=ack(journal,fixture);journal.fault=fault
                    denied(journal.import_fixture_pins,checkpoint)
                assert journal.poisoned
                before=snapshot(fixture[0]/a.NAME)
                denied(ack,journal,fixture)
                denied(journal.import_fixture_pins,())
                assert snapshot(fixture[0]/a.NAME)==before
                journal.close()
            pins=journal_pins(fixture[0]); before=snapshot(fixture[0]/a.NAME)
            result=observe(fixture,pins)
            if phase in ('final-fsync','before-return'):
                assert result['state']=='fixture-records-observed-not-recovered'
                assert result['complete_records']=={'intent':1,'ack':2,'import':3}[record]
            else: assert result['state']=='unknown'
            denied(create,fixture)
            assert snapshot(fixture[0]/a.NAME)==before

    # A syscall can complete but report an error to the caller: visible final
    # bytes still cannot recover the missing successful return/checkpoint.
    fixture=fixtures('fsync-uncertain');journal=create(fixture)
    original_fsync=os.fsync;calls=[0]
    def uncertain_fsync(fd):
        original_fsync(fd);calls[0]+=1
        if calls[0]==3: raise OSError('completion of final fsync not known to caller')
    with mock.patch.object(a.os,'fsync',side_effect=uncertain_fsync): denied(ack,journal,fixture)
    assert calls[0]==3 and journal.poisoned and journal.checkpoint is None
    pins=journal_pins(fixture[0]);journal.close()
    assert observe(fixture,pins)['complete_records']==2
    denied(create,fixture)

    for record in ('ack','import'):
        fixture=fixtures('return-race-'+record);journal=create(fixture)
        def corrupt(point):
            if point==record+'-before-return':
                file=fixture[0]/a.NAME/(record+'.json');file.write_bytes(file.read_bytes()+b' ')
        if record=='ack':
            journal.fault=corrupt;denied(ack,journal,fixture)
            assert journal.checkpoint is None
        else:
            checkpoint=ack(journal,fixture);journal.fault=corrupt
            denied(journal.import_fixture_pins,checkpoint)
            assert not journal.imported
        assert journal.poisoned
        journal.close()

    # Replacement/corruption before explicit import freezes the live writer.
    for target in ('parent','root','lease','intent','ack','extra'):
        fixture=fixtures('replace-'+target); journal=create(fixture)
        checkpoint=ack(journal,fixture); path=fixture[0]/a.NAME
        if target=='parent':
            fixture[0].rename(root/'retained-parent');fixture[0].mkdir(mode=0o700)
        elif target=='root': path.rename(fixture[0]/'retained-root');path.mkdir(mode=0o700)
        elif target=='lease':
            (path/'lease.lock').rename(path/'retained-lease')
            fd=os.open(path/'lease.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        elif target in ('intent','ack'):
            file=path/(target+'.json'); file.write_bytes(file.read_bytes()+b' ')
        else: (path/'foreign').write_bytes(b'foreign')
        denied(journal.import_fixture_pins,checkpoint)
        assert journal.poisoned
        assert not (path/'import.json').exists()
        journal.close()

    # Observer rejects context changes, malformed records and object aliases.
    for target in ('request','pins','ack-link','ack-schema','ack-enable','ack-context','import-linkage','extra'):
        fixture=fixtures('observe-'+target);journal=create(fixture)
        checkpoint=ack(journal,fixture);safe(journal.import_fixture_pins(checkpoint))
        pins=journal_pins(fixture[0]);journal.close();path=fixture[0]/a.NAME
        if target=='request':
            changed=json.loads(fixture[2]);changed['attempt']='2'*32
            fixture=(*fixture[:2],b.canonical(changed),*fixture[3:])
        elif target=='pins': pins=(*pins[:3],pins[3]+1)
        elif target=='ack-link': os.link(path/'ack.json',fixture[0]/'alias')
        elif target.startswith('ack-'):
            file=path/'ack.json'; changed=json.loads(file.read_bytes())
            if target=='ack-schema': changed['schema']=True
            if target=='ack-enable': changed['admission_enabled']=True
            if target=='ack-context': changed['intent_sha256']='0'*64
            file.write_bytes(b.canonical(changed))
        elif target=='import-linkage':
            file=path/'import.json';changed=json.loads(file.read_bytes());changed['ack_sha256']='0'*64
            file.write_bytes(b.canonical(changed))
        else: (path/'foreign').write_bytes(b'foreign')
        assert observe(fixture,pins)['state']=='unknown'

    # Process death after full ACK publication but before its return is unknown.
    fixture=fixtures('killed');left,right=socket.socketpair()
    pid=os.fork()
    if pid==0:
        left.close()
        def paused(point):
            if point=='ack-before-return':
                right.sendall(b'R');right.recv(1)
        try:
            journal=create(fixture,fault=paused);ack(journal,fixture)
            os._exit(3)
        except BaseException: os._exit(4)
    right.close()
    try:
        ready,_,_=select.select([left],[],[],5)
        assert ready and left.recv(1)==b'R'
        pins=journal_pins(fixture[0])
        assert observe(fixture,pins)['state']=='lease-held'
    finally:
        os.kill(pid,signal.SIGKILL);os.waitpid(pid,0);left.close()
    assert observe(fixture,pins)['state']=='fixture-records-observed-not-recovered'
    assert observe(fixture,pins)['complete_records']==2
    denied(create,fixture)

source=Path(a.__file__).read_text()
for forbidden in ('import subprocess','import socket','import controller','import receipt_store',
                  'def resume','def reset','def reopen','LOCK_UN','os.system','os.exec'):
    assert forbidden not in source
print('PASS local bootstrap ACK host reference: intent/ACK/import barriers, caller-held live checkpoint, durable-publication faults, SIGKILL, frozen errors and read-only non-recovery; no activation/device transport')
