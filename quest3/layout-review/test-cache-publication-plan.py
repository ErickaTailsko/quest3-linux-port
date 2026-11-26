#!/usr/bin/env python3
"""Host interval ledger tests, no byte readback, cache maintenance or helper."""
from dataclasses import replace
from pathlib import Path
import random

import cache_publication_plan as c
import relocation_plan as s
import returned_layout as r

BOOT='a'*32;ATTEMPT='b'*32;BASE=64*r.GIB
RESOURCES=tuple(c.Resource(kind,f'{index+1:032x}',BASE+index*4*r.MIB,
    r.ALIGN if kind in ('image','initrd','dtb') else r.PAGE,
    0x80000 if kind=='image' else 0,
    8192 if kind=='image' else 400 if kind=='code' else r.PAGE) for index,kind in enumerate(c.KINDS))


def event(kind,a=None,offset=0,size=0):
    return c.Event(kind,BOOT,ATTEMPT,a.allocation_id if a else '',offset,size)


def fixture(dline=64,iline=64):
    trace=[event('observer-ack-claimed')]
    for a in RESOURCES:
        # Deliberately unaligned byte writes exercise line sharing/tails.
        trace.extend((event('write-claimed',a,a.required_offset,17),
                      event('write-claimed',a,a.required_offset+17,a.required_bytes-17)))
        lo,hi=c._round((a.required_offset,a.required_offset+a.required_bytes),dline)
        trace.append(event('poc-claimed',a,lo,hi-lo))
    code=RESOURCES[3];lo,hi=c._round((0,code.required_bytes),iline)
    trace.extend((event('icache-claimed',code,lo,hi-lo),event('coverage-checkpoint')))
    return tuple(trace)


def review(trace,resources=RESOURCES,**kwargs):
    result=c.review(resources,trace,boot=BOOT,attempt=ATTEMPT,**kwargs)
    for field in (*s.flags(),'fixture_claims_are_runtime_evidence','cache_protocol_verified',
                  'authorization_verified','helper_implemented'):
        assert result[field] is False
    return result


def denied(trace,**kwargs):
    try: review(trace,**kwargs)
    except ValueError: return
    raise AssertionError('invalid interval/publication claim accepted')


TRACE=fixture();assert review(TRACE)['coverage_claims_complete']
assert review(TRACE)['code_icache_intervals_claimed']==[[0,448]]
assert review(tuple(replace(e) for e in TRACE))==review(TRACE)  # Replay is NOT history/lifetime evidence.
for dline in (16,32,64,128,256):
    for iline in (16,32,64,128,256):
        assert review(fixture(dline,iline),dcache_line=dline,icache_line=iline)['coverage_claims_complete']
for a in RESOURCES:
    prefix=TRACE+(event('write-claimed',a,a.required_offset+23,1),)
    result=review(prefix)
    assert not result['coverage_claims_complete'] and not result['no_dirty_dcache_lines_claimed']
    row=next(row for row in result['resources'] if row['kind']==a.kind)
    assert row['dirty_dcache_intervals']==[[a.required_offset,a.required_offset+64]]
    denied(prefix+(event('coverage-checkpoint'),))
    republished=prefix+(event('poc-claimed',a,a.required_offset,64),)
    if a.kind=='code':
        assert not review(republished)['code_icache_coverage_claimed']
        republished+=(event('icache-claimed',a,0,448),)
    assert review(republished+(event('coverage-checkpoint'),))['coverage_claims_complete']

# Cleaning early cannot initialize bytes; later writes invalidate that clean.
early=[]
for a in RESOURCES:
    lo,hi=c._round((a.required_offset,a.required_offset+a.required_bytes),64)
    early.append(event('poc-claimed',a,lo,hi-lo))
early=tuple(early)
assert not review(early)['required_bytes_written_claimed']
denied(early+(event('coverage-checkpoint'),))
late_writes=tuple(e for e in TRACE if e.kind=='write-claimed')
assert not review(early+late_writes)['no_dirty_dcache_lines_claimed']
denied(early+late_writes+(event('coverage-checkpoint'),))
for i,e in enumerate(TRACE):
    if e.kind in ('write-claimed','poc-claimed','icache-claimed'):
        denied(TRACE[:i]+TRACE[i+1:])
        for field,value in (('size',0),('size',True),('size',1<<64),('offset',-1),
                            ('boot','c'*32),('attempt','c'*32),('allocation_id','f'*32)):
            denied(TRACE[:i]+(replace(e,**{field:value}),)+TRACE[i+1:])
image=RESOURCES[0];code=RESOURCES[3]
denied((event('write-claimed',image,0,1),))
denied((event('write-claimed',image,image.required_offset+image.required_bytes,1),))
denied((event('poc-claimed',code,1,64),))
denied((event('icache-claimed',code,0,448),))
denied(TRACE[:-2]+(event('icache-claimed',image,0,64),))
denied(TRACE[:-2]+(event('icache-claimed',code,0,64),event('coverage-checkpoint')))
# Clean all but the last D-cache line; partial cover never becomes publication.
bad=list(TRACE);i=next(i for i,e in enumerate(bad) if e.kind=='poc-claimed' and e.allocation_id==image.allocation_id)
bad[i]=replace(bad[i],size=bad[i].size-64);denied(tuple(bad))

for fence in c.FENCES:
    fenced=TRACE+(event(fence),)
    assert fence in review(fenced)['declared_fences']
    denied(fenced+(event(fence),));denied(fenced+(event('observer-ack-claimed'),))
    state=review(fenced+(event('known-failure'),))['state']
    assert state==('FAILED_AFTER_IRREVERSIBLE' if fence in ('no-inverse-attempt','global-shutdown') else 'FAILED_RETAINED')
late_code=TRACE+(event('global-shutdown'),event('write-claimed',code,17,1))
assert not review(late_code)['coverage_claims_complete']  # Arithmetic only, NOT permission for a late rewrite.
denied(late_code+(event('coverage-checkpoint'),))
for end in range(len(TRACE)+1):
    for reason in c.UNKNOWN+('known-failure',):
        terminal=TRACE[:end]+(event(reason),)
        assert review(terminal)['terminal']
        for extra in (event('coverage-checkpoint'),event('cleanup'),event('read'),event('resume'),TRACE[1]):
            denied(terminal+(extra,))

for invalid in (True,0,15,48,512): denied(TRACE,dcache_line=invalid);denied(TRACE,icache_line=invalid)
for resources in (RESOURCES[:5],list(RESOURCES),RESOURCES[:5]+(RESOURCES[0],),
                  (replace(image,physical_start=RESOURCES[1].physical_start),)+RESOURCES[1:],
                  (replace(image,physical_start=BASE+1),)+RESOURCES[1:],
                  (replace(image,allocation_id=BOOT),)+RESOURCES[1:],
                  (replace(image,required_bytes=True),)+RESOURCES[1:],
                  (replace(image,required_bytes=r.ALIGN),)+RESOURCES[1:],
                  (replace(image,physical_start=r.PHYS_LIMIT),)+RESOURCES[1:],
                  (replace(image,provenance='runtime-owned'),)+RESOURCES[1:]):
    denied(TRACE,resources=resources)
denied(list(TRACE));denied((TRACE[0],)*(c.MAX_EVENTS+1))

# Independent byte/line-set oracle for repeated writes and fragmented cleans.
rng=random.Random(181126);oracle_written=set();oracle_dirty=set();trace=[]
for _ in range(300):
    if rng.randrange(2):
        offset=rng.randrange(image.required_bytes);size=rng.randint(1,min(200,image.required_bytes-offset))
        trace.append(event('write-claimed',image,image.required_offset+offset,size))
        oracle_written.update(range(offset,offset+size))
        oracle_dirty.update(range(offset//64,(offset+size-1)//64+1))
    else:
        line=rng.randrange(image.required_bytes//64);count=rng.randint(1,image.required_bytes//64-line)
        trace.append(event('poc-claimed',image,image.required_offset+line*64,count*64))
        oracle_dirty.difference_update(range(line,line+count))
    row=review(tuple(trace))['resources'][0]
    actual_written={n-image.required_offset for lo,hi in row['written_intervals'] for n in range(lo,hi)}
    actual_dirty={n-image.required_offset//64 for lo,hi in row['dirty_dcache_intervals'] for n in range(lo//64,hi//64)}
    assert actual_written==oracle_written and actual_dirty==oracle_dirty

source=Path(c.__file__).read_text()
for forbidden in ('import os','import socket','import subprocess','open(', 'exec(', 'eval(',
                  'def write','def execute','def acquire','def release','import controller'):
    assert forbidden not in source
print('PASS host publication ledger: full-allocation aliases, byte initialization, per-line stale clean invalidation, code I-cache, independent boundaries, terminal uncertainty and seeded byte/line oracle; no helper or runtime evidence')
