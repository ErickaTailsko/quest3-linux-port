#!/usr/bin/env python3
"""Host claim traces only. No real handles, I/O, cache instructions or writes."""
from dataclasses import replace
from pathlib import Path
import random

import direct_staging_trace as t
import relocation_plan as s
import returned_layout as r

BOOT='a'*32
ATTEMPT='b'*32
SEGMENTS=tuple(t.Segment(role,7,r.PAGE) for role in r.PROVIDERS)


def event(kind,**kwargs): return t.Event(kind,BOOT,ATTEMPT,**kwargs)


def fixture():
    result=[event('prepare',claims=t.PREPARE_CLAIMS)]
    for seg in SEGMENTS:
        # First read is short but positive: only three bytes become available.
        for offset,requested,completed in ((0,7,3),(3,4,4)):
            result.extend((event('read-request',role=seg.role,offset=offset,amount=requested),
                           event('read-complete',role=seg.role,offset=offset,amount=completed),
                           event('copy-complete',role=seg.role,offset=offset,amount=completed)))
        result.append(event('zero-complete',role=seg.role,offset=7,amount=r.PAGE-7))
    result.extend((event('seal',claims=t.SEAL_CLAIMS),
                   event('irreversible-boundary',claims=t.SHUTDOWN_CLAIMS),
                   event('final-clean',claims=t.CLEAN_CLAIMS),
                   event('entry-described',claims=('dedicated-no-copy-path-reviewed',))))
    return tuple(result)


def review(events,segments=SEGMENTS,**kwargs):
    result=t.review(segments,events,boot=BOOT,attempt=ATTEMPT,**kwargs)
    for field in (*s.flags(),'cache_protocol_verified','target_readback_verified',
                  'authorization_verified','direct_writer_implemented','streaming_io_implemented',
                  'fixture_claims_are_runtime_evidence'):
        assert result[field] is False
    return result


def denied(events,**kwargs):
    try: review(events,**kwargs)
    except ValueError: return
    raise AssertionError('invalid host claim trace accepted')


TRACE=fixture()
assert review(TRACE)['state']=='ENTRY_DESCRIBED'
assert review(TRACE)['full_entry_trace_described']
assert review(TRACE)['copied_bytes_claimed']==dict.fromkeys(r.PROVIDERS,7)
assert review(TRACE)['zeroed_bytes_claimed']==dict.fromkeys(r.PROVIDERS,r.PAGE-7)
assert review(tuple(replace(e) for e in TRACE))==review(TRACE)  # Replay equality proves no physical lifetime/history.
for end in range(len(TRACE)+1):
    result=review(TRACE[:end])
    assert result['full_entry_trace_described']==(end==len(TRACE))
    # Every uncertainty reason at every nonterminal prefix freezes all later
    # operations, including purported reads, recovery, cleanup and fallback.
    if end==len(TRACE): continue
    for reason in t.UNCERTAIN+t.FAILURES:
        frozen=TRACE[:end]+(event(reason),)
        assert review(frozen)['terminal']
        crossed=any(e.kind=='irreversible-boundary' for e in TRACE[:end])
        assert review(frozen)['irreversible_boundary_claimed']==crossed
        assert review(frozen)['state']==('FROZEN_UNKNOWN' if reason in t.UNCERTAIN else
                                          'FAILED_AFTER_IRREVERSIBLE' if crossed else 'FAILED_RETAINED')
        for command in ('read-request','cleanup','retry','fallback','resume','prepare','final-clean'):
            denied(frozen+(event(command),))

for index,e in enumerate(TRACE):
    if e.kind!='entry-described': denied(TRACE[:index]+TRACE[index+1:])
    if e.claims:
        for claim in e.claims:
            denied(TRACE[:index]+(replace(e,claims=tuple(c for c in e.claims if c!=claim)),)+TRACE[index+1:])
        denied(TRACE[:index]+(replace(e,claims=e.claims+('unreviewed',)),)+TRACE[index+1:])
        denied(TRACE[:index]+(replace(e,claims=e.claims+(e.claims[0],)),)+TRACE[index+1:])
    for field,value in (('boot','c'*32),('attempt','c'*32),('amount',True),('offset',-1),('claims',[])):
        denied(TRACE[:index]+(replace(e,**{field:value}),)+TRACE[index+1:])

denied(TRACE[1:])  # Write/read before preparation.
denied(TRACE+(event('entry-described'),))
for index in (1,2,3):
    for amount in (0,8,r.PAGE+1,1<<64):
        denied(TRACE[:index]+(replace(TRACE[index],amount=amount),)+TRACE[index+1:])
    denied(TRACE[:index]+(replace(TRACE[index],offset=1),)+TRACE[index+1:])
assert review(TRACE[:2]+(replace(TRACE[2],amount=0),))['state']=='FAILED_RETAINED'
assert not review(TRACE[:2]+(replace(TRACE[2],amount=0),))['pending_read_claimed']
assert review(TRACE[:2])['pending_read_claimed']
assert review(TRACE[:3])['buffer_bytes_pending_copy_claimed']==3
assert not review(TRACE[:3])['pending_read_claimed']
denied(TRACE[:2]+(TRACE[1],))  # Second request while first is outstanding.
denied(TRACE[:3]+(TRACE[1],))  # Buffer reuse before copy completion.
denied(TRACE[:2]+(replace(TRACE[2],role='initrd'),))
denied(TRACE[:1]+(event('zero-complete',role='image',offset=7,amount=r.PAGE-7),))
for e in (event('copy-complete',role='image',amount=1),
          event('zero-complete',role='image',offset=r.PAGE,amount=1),
          event('read-request',role='image',amount=1),event('prepare',claims=t.PREPARE_CLAIMS)):
    for end in (len(TRACE)-3,len(TRACE)-2,len(TRACE)-1): denied(TRACE[:end]+(e,))

for buffer in (True,0,r.PAGE-1,r.PAGE+1,r.ALIGN+r.PAGE): denied(TRACE,buffer_bytes=buffer)
for segments in (SEGMENTS[:2],list(SEGMENTS),SEGMENTS[:2]+(SEGMENTS[0],),
                 (replace(SEGMENTS[0],stage_bytes=r.PAGE-1),)+SEGMENTS[1:],
                 (replace(SEGMENTS[0],file_bytes=True),)+SEGMENTS[1:],
                 (replace(SEGMENTS[0],file_bytes=r.PAGE+1),)+SEGMENTS[1:]):
    denied(TRACE,segments=segments)
denied(list(TRACE));denied((TRACE[0],)*(t.MAX_EVENTS+1))

# Random permutations cannot bypass ordering. Some swaps may be equivalent
# across independent segments; every accepted trace still has false runtime gates.
rng=random.Random(180026)
for _ in range(50):
    segments=(t.Segment('image',5000,8192),t.Segment('initrd',1,4096),t.Segment('dtb',4096,4096))
    trace=[TRACE[0]]
    for seg in segments:
        offset=0
        while offset<seg.file_bytes:
            request=min(r.PAGE,seg.file_bytes-offset)
            completed=rng.randint(1,request)
            trace.extend((event('read-request',role=seg.role,offset=offset,amount=request),
                          event('read-complete',role=seg.role,offset=offset,amount=completed),
                          event('copy-complete',role=seg.role,offset=offset,amount=completed)))
            offset+=completed
        while offset<seg.stage_bytes:
            amount=min(r.PAGE,seg.stage_bytes-offset)
            trace.append(event('zero-complete',role=seg.role,offset=offset,amount=amount))
            offset+=amount
    trace.extend(TRACE[-4:])
    assert review(tuple(trace),segments=segments)['full_entry_trace_described']

for _ in range(500):
    shuffled=list(TRACE);rng.shuffle(shuffled)
    try: review(tuple(shuffled))
    except ValueError: pass

source=Path(t.__file__).read_text()
for forbidden in ('import os','import socket','import subprocess','open(', 'exec(', 'eval(',
                  'def write','def execute','def acquire','def release','import controller'):
    assert forbidden not in source
print('PASS direct staging HOST traces: bounded short reads/copy/zero progress, phase claims, sealing/cache ordering, terminal failure/uncertainty and no runtime evidence or writer')
