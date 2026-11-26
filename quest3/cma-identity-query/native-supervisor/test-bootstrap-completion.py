#!/usr/bin/env python3
"""Pure supplied-byte completion/restart contract cases; no actions or state writes."""
import base64
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import bootstrap_completion_draft as m
import bootstrap_receipt as b
from transport_protocol import PREFIX


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except ValueError: pass
    else: raise AssertionError('invalid completion/checkpoint context accepted')


request=b.canonical(dict(schema=1,profile=b.PROFILE,execution_enabled=False,
    boot='00000000-0000-0000-0000-000000000001',attempt='a'*32,bootstrap_operation='1'*32,
    authorization_sha256='b'*64,device_binding_sha256='c'*64,helper_sha256='d'*64,
    local_intent_sha256='e'*64,module_sha256='f'*64,parent_dev=7,parent_ino=101))
receipt=b.canonical(dict(schema=1,profile=b.PROFILE,producer='host-native-bootstrap-reference',
    admission_enabled=False,bootstrap_phase='metadata-only-no-activation',execution_enabled=False,
    local_pin_ack_verified=False,request=b.parse_request(request),request_sha256=b.request_commitment(request),
    root_dev=7,root_ino=102,lease_dev=7,lease_ino=103))
token='2'*32; local_pins=[8,201,8,202,8,203]; peer_pins=[7,102,7,103]
pending=m.create_pending(request,token,'3'*64,local_pins)
reply=('ERIS_BOOTSTRAP_RECEIPT '+'1'*32+' '+hashlib.sha256(receipt).hexdigest()+'\n').encode()
frame=PREFIX+token.encode()+b' 0\n'; wire=reply+frame
boot=b.parse_request(request)['boot']; boots=[boot,boot]
transport=dict(kind='exit',returncode=0,foreground_reaped=True,streams_complete=True,interrupted=False)
stderr=b'fixture diagnostic\x00\xff'


def complete(active_pending=pending,active_receipt=receipt,active_wire=wire,active_stderr=stderr,**kwargs):
    return m.create_completion(active_pending,active_receipt,active_wire,active_stderr,
                               boot_samples=kwargs.get('boot_samples',boots),transport=kwargs.get('transport',transport))


completion=complete(); ack_sha='4'*64
checkpoint=m.create_checkpoint_draft(pending,completion,ack_sha)
anchor=m.checkpoint_commitment(pending,completion,checkpoint)
assert m.pending_commitment(pending)=='d387e9e56d4f7e8d6d223d1cba3c0b35faaa198d2df63cf65a7d9ebbe6fe2a93'
assert m.completion_commitment(pending,completion)=='086aee679f50280b8c1fa4dc663e6abc607561137ee72b41e82423cc0ced5ee6'
assert anchor=='24542385e271138006bb2eaa9763446929908d85ff3cc7bc2f79b3cc84f0013d'


def review(p=pending,c=completion,cp=checkpoint,**kwargs):
    return m.review_restart(p,c,cp,caller_checkpoint_sha256=kwargs.get('caller_checkpoint_sha256',anchor),
        observed_ack_sha256=kwargs.get('observed_ack_sha256',ack_sha),
        observed_local_journal_pins=kwargs.get('observed_local_journal_pins',local_pins),
        observed_peer_pins=kwargs.get('observed_peer_pins',peer_pins),boot_sample=kwargs.get('boot_sample',boot))


result=review()
assert result['logical_links_verified'] and result['caller_anchor_matched'] and result['observed_ack_bytes_match']
for key in (*m.flags(),'external_anchor_provenance_verified','external_anchor_durability_verified',
            'historical_completion_proven','writer_recovered'):
    assert result[key] is False
assert result['state']=='anchored-bytes-consistent-no-resume'
assert 'checkpoint' not in result
assert base64.b64decode(json.loads(completion)['stderr_b64'])==stderr
assert len({m.pending_commitment(pending),m.completion_commitment(pending,completion),anchor})==3

# Neither EOF/local exit zero nor a raw bootstrap reply proves framed completion.
for bad_wire in (b'',reply,frame,wire[:-1],wire+b'junk',wire+frame,
                 wire.replace(token.encode(),b'5'*32),wire.replace(b' 0\n',b' 125\n'),
                 wire.replace(b' 0\n',b' 126\n'),wire.replace(b' 0\n',b' 23\n'),
                 wire.replace(b' 0\n',b' 00\n'),wire.replace(b'1'*32,b'6'*32),b'x'*1048577):
    denied(complete,pending,receipt,bad_wire)
for changes in (dict(kind='timeout'),dict(kind='signal',returncode=15),dict(returncode=1),
                dict(returncode=False),dict(foreground_reaped=False),dict(streams_complete=False),
                dict(interrupted=True),dict(unexpected=True),dict(foreground_reaped=1)):
    denied(complete,transport=dict(transport,**changes))
denied(complete,transport='host-fixture-complete')
for samples in (None,[],[boot],[boot,boot,boot],[boot,'new-boot'],['new-boot',boot]):
    denied(complete,boot_samples=samples)
denied(complete,pending,receipt,wire,b'x'*65537)
denied(complete,pending,receipt,wire,'not bytes')
for nonce in ('a'*32,'1'*32,'A'*32,None):
    denied(m.create_pending,request,nonce,'3'*64,local_pins)
for pins in ([8,201,8,201,8,203],[8,201,9,202,8,203],[8,True,8,202,8,203],[],[8,0,8,202,8,203]):
    denied(m.create_pending,request,token,'3'*64,pins)

# Each supplied-record field is committed exactly, with no type coercion.
for field,replacement in (('schema',True),('execution_enabled',True),('role','run-command'),
                           ('transport_token','5'*32),('request_sha256','0'*64)):
    changed=json.loads(pending);changed[field]=replacement
    if field=='transport_token':
        changed=b.canonical(changed)
        denied(complete,changed)
    else: denied(m.pending_commitment,b.canonical(changed))
for field,replacement in (('remote_status',False),('stderr_size',True),('stderr_sha256','0'*64),
                           ('stderr_b64','!!'),('pending_sha256','0'*64),('reply_sha256','0'*64),
                           ('admission_enabled',True),('candidate_pins',[7,102,7,104])):
    changed=json.loads(completion);changed[field]=replacement
    denied(m.completion_commitment,pending,b.canonical(changed))
for bad in (pending+b'\n',pending.replace(b'"schema":1',b'"schema":1,"schema":1'),b'x'*m.LIMIT):
    denied(m.pending_commitment,bad)

# No restart acceptance from absent/self-selected anchors or mismatched context.
for field,value in (('caller_checkpoint_sha256',None),('caller_checkpoint_sha256','0'*64),
                    ('observed_ack_sha256','0'*64),('observed_peer_pins',[7,102,7,104]),
                    ('observed_local_journal_pins',[8,201,8,202,8,204]),('boot_sample','new-boot')):
    denied(review,**{field:value})
for field,replacement in (('schema',True),('local_ack_sha256','0'*64),('receipt_sha256','0'*64),
                           ('automatic_resume_allowed',True),('completion_sha256','0'*64)):
    changed=json.loads(checkpoint);changed[field]=replacement
    denied(review,pending,completion,b.canonical(changed))

# Recalculating public hashes can forge a whole unanchored story. The old
# independent anchor rejects it; selecting the new digest proves only consistency.
rewritten_completion=complete(active_stderr=b'rewritten diagnostics')
rewritten_checkpoint=m.create_checkpoint_draft(pending,rewritten_completion,'6'*64)
denied(review,pending,rewritten_completion,rewritten_checkpoint,observed_ack_sha256='6'*64)
rewritten_anchor=m.checkpoint_commitment(pending,rewritten_completion,rewritten_checkpoint)
untrusted=review(pending,rewritten_completion,rewritten_checkpoint,
                 caller_checkpoint_sha256=rewritten_anchor,observed_ack_sha256='6'*64)
assert not untrusted['external_anchor_provenance_verified']
assert not untrusted['historical_completion_proven'] and not untrusted['automatic_resume_allowed']

# A changed device/boot/attempt context cannot inherit an old completion/anchor.
for key,value in (('boot','00000000-0000-0000-0000-000000000002'),('attempt','7'*32),
                  ('helper_sha256','8'*64),('authorization_sha256','9'*64),('parent_ino',104)):
    changed=b.parse_request(request);changed[key]=value
    another=m.create_pending(b.canonical(changed),token,'3'*64,local_pins)
    denied(m.completion_commitment,another,completion)

source=Path(m.__file__).read_text()
for forbidden in ('import os','import subprocess','import socket','open(', 'exec(', 'eval(',
                  'import controller','import bootstrap_ack_reference'):
    assert forbidden not in source
print('PASS bootstrap completion draft: original nonce/status frame, supplied wait/streams/boot context, exact captures, external checkpoint comparison and rewritten-tail limits; no I/O/resume/admission')
