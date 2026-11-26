#!/usr/bin/env python3
"""Bound host fixture timeline, never a writer or runtime admission test."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import struct

import staging_binding_review as b
import cache_publication_plan as c
import direct_staging_trace as t
import returned_layout as r
import relocation_plan as s

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('binding_layout_cases',here/'test-returned-layout.py')
cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)
BOOT='b'*32;ATTEMPT=cases.ATTEMPT


def phase(kind,**kwargs): return t.Event(kind,BOOT,ATTEMPT,**kwargs)
def pub(kind,a=None,offset=0,size=0): return c.Event(kind,BOOT,ATTEMPT,a.allocation_id if a else '',offset,size)


def fixture(offset=0x80000,*,k=None,rd=b'fixture-initrd',tree=None,buffer_bytes=r.PAGE):
    image=cases.image(size=3*r.PAGE,offset=offset,file_bytes=r.PAGE+17) if k is None else k
    initrd=rd;image_offset,image_size=struct.unpack_from('<QQ',image,8)
    allocations=cases.allocations()
    allocations[0]=replace(allocations[0],allocated_bytes=r._up(image_offset+r._up(image_size,r.PAGE),r.ALIGN))
    tree,layout=r.prepare_dtb(image,initrd,cases.dtb() if tree is None else tree,allocations,attempt=ATTEMPT)
    resources=[]
    for slot in layout['slots']:
        start=int(slot['allocation_start'],16)
        resources.append(c.Resource(slot['role'],slot['allocation_id'],start,slot['allocation_bytes'],
            int(slot['payload_start'],16)-start,slot['stage_bytes']))
    for i,kind in enumerate(('code','pgd','pud')):
        resources.append(c.Resource(kind,f'{100+i:032x}',cases.BASE+2*r.GIB+i*r.PAGE,r.PAGE,0,400 if kind=='code' else r.PAGE))
    resources=tuple(resources);steps=[phase('prepare',claims=t.PREPARE_CLAIMS)]
    for slot in layout['slots']:
        position=0
        while position<slot['file_bytes']:
            amount=min(buffer_bytes,slot['file_bytes']-position)
            steps.extend((phase('read-request',role=slot['role'],offset=position,amount=amount),
                          phase('read-complete',role=slot['role'],offset=position,amount=amount),
                          phase('copy-complete',role=slot['role'],offset=position,amount=amount)))
            position+=amount
        while position<slot['stage_bytes']:
            amount=min(buffer_bytes,slot['stage_bytes']-position)
            steps.append(phase('zero-complete',role=slot['role'],offset=position,amount=amount));position+=amount
    for a in resources[3:]: steps.append(pub('write-claimed',a,0,a.required_bytes))
    steps.extend((phase('seal',claims=t.SEAL_CLAIMS),pub('observer-ack-claimed'),pub('observer-frozen'),
                  pub('transport-lost'),phase('irreversible-boundary',claims=t.SHUTDOWN_CLAIMS),
                  pub('no-inverse-attempt'),pub('global-shutdown')))
    for a in resources:
        lo,hi=c._round((a.required_offset,a.required_offset+a.required_bytes),64)
        steps.append(pub('poc-claimed',a,lo,hi-lo))
    steps.extend((pub('icache-claimed',resources[3],0,448),phase('final-clean',claims=t.CLEAN_CLAIMS),
                  phase('entry-described',claims=('dedicated-no-copy-path-reviewed',))))
    return (image,initrd,tree,allocations,resources,tuple(steps))


def review(data,**kwargs):
    result=b.review(*data,boot=BOOT,attempt=ATTEMPT,**kwargs)
    for field in (*s.flags(),'fixture_claims_are_runtime_evidence','authorization_verified','target_readback_verified',
                  'cache_protocol_verified','helper_implemented','direct_writer_implemented',
                  'streaming_io_implemented','runtime_admission_enabled'):
        assert result[field] is False
    return result


def denied(data,**kwargs):
    try: review(data,**kwargs)
    except ValueError: return
    raise AssertionError('inconsistent bound fixture accepted')


DATA=fixture();TRACE=DATA[-1];RESOURCES=DATA[-2];result=review(DATA)
assert result['full_fixture_description'] and result['fixture_bindings_match']
assert result['dynamic_reservations_unresolved']==['/reserved-memory/fixture-dynamic']
assert result['derived_payload_write_links'][0]['offset']==0x80000
assert result['publication']['coverage_checkpoints']==1
assert review(fixture(offset=0))['full_fixture_description']
assert review((*DATA[:-1],tuple(replace(e) for e in TRACE)))==result  # Consistent replay is NOT history/lifetime.
short=(phase('read-request',role='image',offset=0,amount=r.PAGE),
       phase('read-complete',role='image',offset=0,amount=17),
       phase('copy-complete',role='image',offset=0,amount=17),
       phase('read-request',role='image',offset=17,amount=r.PAGE-17),
       phase('read-complete',role='image',offset=17,amount=r.PAGE-17),
       phase('copy-complete',role='image',offset=17,amount=r.PAGE-17))
short_result=review((*DATA[:-1],TRACE[:1]+short+TRACE[4:]))
assert short_result['full_fixture_description'] and short_result['derived_payload_write_links'][0]['size']==17
optional=tuple(e for e in TRACE if not (type(e) is c.Event and e.kind in ('observer-frozen','transport-lost','no-inverse-attempt')))
assert review((*DATA[:-1],optional))['full_fixture_description']

for end in range(len(TRACE)+1):
    prefix=(*DATA[:-1],TRACE[:end]);prefix_result=review(prefix)
    assert prefix_result['full_fixture_description']==(end==len(TRACE))
    if end==len(TRACE): continue
    for reason in t.UNCERTAIN+('io-error',):
        failed=(*DATA[:-1],TRACE[:end]+(phase(reason),))
        assert not review(failed)['full_fixture_description']
        assert review(failed)['publication']['terminal']
        denied((*DATA[:-1],failed[-1]+(pub('poc-claimed',RESOURCES[0],0,64),)))

for i,e in enumerate(TRACE):
    if type(e) is c.Event and e.kind not in ('observer-frozen','transport-lost','no-inverse-attempt'):
        denied((*DATA[:-1],TRACE[:i]+TRACE[i+1:]))
    for field,value in (('boot','c'*32),('attempt','c'*32)):
        denied((*DATA[:-1],TRACE[:i]+(replace(e,**{field:value}),)+TRACE[i+1:]))

for field,value in (('allocation_id','f'*32),('physical_start',cases.BASE+4*r.MIB),
                    ('allocated_bytes',2*r.ALIGN),('required_offset',0),('required_bytes',2*r.PAGE)):
    resources=(replace(RESOURCES[0],**{field:value}),)+RESOURCES[1:]
    denied((*DATA[:4],resources,TRACE))
resources=RESOURCES[:3]+(replace(RESOURCES[3],physical_start=cases.BASE+200*r.GIB),)+RESOURCES[4:]
denied((*DATA[:4],resources,TRACE))
tree,_=r.prepare_dtb(DATA[0],DATA[1],cases.dtb(static=[(RESOURCES[3].physical_start,r.PAGE)]),DATA[3],attempt=ATTEMPT)
denied((DATA[0],DATA[1],tree,*DATA[3:]))
denied((DATA[0],DATA[1],cases.dtb(),*DATA[3:]))
allocations=list(DATA[3]);allocations[0]=replace(allocations[0],attempt='c'*32)
denied((*DATA[:3],allocations,*DATA[4:]))

seal=next(i for i,e in enumerate(TRACE) if type(e) is t.Event and e.kind=='seal')
boundary=next(i for i,e in enumerate(TRACE) if type(e) is t.Event and e.kind=='irreversible-boundary')
clean=next(i for i,e in enumerate(TRACE) if type(e) is c.Event and e.kind=='poc-claimed')
codewrite=next(e for e in TRACE if type(e) is c.Event and e.kind=='write-claimed')
for position in (0,seal+1,boundary+1,len(TRACE)-1,len(TRACE)):
    denied((*DATA[:-1],TRACE[:position]+(codewrite,)+TRACE[position:]))
denied((*DATA[:-1],TRACE[:1]+(pub('write-claimed',RESOURCES[0],0x80000,r.PAGE),)+TRACE[1:]))
denied((*DATA[:-1],TRACE[:seal]+(TRACE[clean],)+TRACE[seal:]))
denied((*DATA[:-1],TRACE[:seal]+(pub('observer-ack-claimed'),)+TRACE[seal:]))
denied((*DATA[:-1],TRACE[:clean]+(pub('observer-ack-claimed'),)+TRACE[clean:]))
denied((*DATA[:-1],TRACE+(pub('coverage-checkpoint'),)))
denied((*DATA[:-1],list(TRACE)));denied((*DATA[:-1],(TRACE[0],)*(b.MAX_STEPS+1)))

# Real trim3/initrd bytes, but synthetic padded DT/resources/events. A 64 KiB
# declared buffer fits this bounded composition; 4 KiB full-size traces do not.
LARGE=fixture(k=cases.real_image,rd=cases.real_initrd,tree=cases.dtb(padding=b'x'*698000),buffer_bytes=65536)
large_result=review(LARGE,buffer_bytes=65536)
assert len(LARGE[-1])<b.MAX_STEPS and large_result['full_fixture_description']
assert LARGE[4][0].allocated_bytes==32*r.MIB
assert large_result['input_sha256']['image']==cases.hashlib.sha256(cases.real_image).hexdigest()
denied(LARGE)  # Declaring 4 KiB cannot validate 64 KiB read requests.

source=Path(b.__file__).read_text()
for forbidden in ('import os','import socket','import subprocess','open(', 'exec(', 'eval(',
                  'def write','def execute','def acquire','def release','import controller'):
    assert forbidden not in source
print('PASS HOST bound staging review: exact layout/resources, one ordered timeline, derived payload interval claims, pre-seal code/tables, final coverage at phase boundary and terminal uncertainty; no runtime admission')
