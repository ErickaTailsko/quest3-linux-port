#!/usr/bin/env python3
"""HOST interval/last-write claim ledger. No bytes, helper or cache operations.

Resources and events are synthetic metadata, NOT mappings, handles, authorization
or execution evidence. This separate model does not amend the loader or trace.
"""
from dataclasses import dataclass

import returned_layout as r
from relocation_plan import flags

PROFILE='q3-cache-publication-claims-host-v1'
KINDS=('image','initrd','dtb','code','pgd','pud')
MAX_EVENTS=4096
FENCES=('observer-frozen','transport-lost','no-inverse-attempt','global-shutdown')
UNKNOWN=('timeout','interrupted','journal-failed','completion-unknown','restart')


@dataclass(frozen=True)
class Resource:
    kind: str
    allocation_id: str
    physical_start: int
    allocated_bytes: int
    required_offset: int
    required_bytes: int
    provenance: str = 'host-fixture-only'


@dataclass(frozen=True)
class Event:
    kind: str
    boot: str
    attempt: str
    allocation_id: str = ''
    offset: int = 0
    size: int = 0


def _union(spans,new):
    result=[]
    for lo,hi in sorted((*spans,new)):
        if result and lo<=result[-1][1]: result[-1]=(result[-1][0],max(result[-1][1],hi))
        else: result.append((lo,hi))
    return result


def _subtract(spans,cut):
    result=[];lo,hi=cut
    for start,end in spans:
        if end<=lo or hi<=start: result.append((start,end))
        else:
            if start<lo: result.append((start,lo))
            if hi<end: result.append((hi,end))
    return result


def _covers(spans,needed): return any(lo<=needed[0] and needed[1]<=hi for lo,hi in spans)


def _round(span,line): return (span[0]//line*line,r._up(span[1],line))


def review(resources,events,*,boot,attempt,dcache_line=64,icache_line=64):
    """Check only supplied interval claims, including stale-clean invalidation.

    Line sizes are assumptions, not CPU queries. Writes after clean are allowed
    as dirty claims requiring republication; this does NOT permit mutation after
    the separate direct-staging trace's content seal. There is no I/O or entry API.
    """
    r._nonce(boot);r._nonce(attempt)
    if boot==attempt: raise ValueError('distinct fixture contexts required')
    for line in (dcache_line,icache_line):
        if type(line) is not int or line not in (16,32,64,128,256):
            raise ValueError('explicit bounded power-of-two line-size assumption required')
    if (type(resources) is not tuple or len(resources)!=len(KINDS) or
            any(type(a) is not Resource or type(a.kind) is not str or a.kind not in KINDS for a in resources) or
            {a.kind for a in resources}!=set(KINDS)):
        raise ValueError('six typed synthetic payload/code/table resources required')
    ids=[boot,attempt];spans=[]
    for a in resources:
        r._nonce(a.allocation_id);ids.append(a.allocation_id)
        end=r._end(a.physical_start,a.allocated_bytes)
        cap=32*r.MIB if a.kind=='image' else r.ALIGN if a.kind in ('initrd','dtb') else r.PAGE
        if (not a.physical_start or a.physical_start%r.PAGE or a.allocated_bytes%r.PAGE or
                a.allocated_bytes>cap or a.provenance!='host-fixture-only' or
                type(a.required_offset) is not int or type(a.required_bytes) is not int or
                not 0<=a.required_offset<a.allocated_bytes or
                not 0<a.required_bytes<=a.allocated_bytes-a.required_offset):
            raise ValueError('invalid allocation/required interval or fixture provenance')
        spans.append((a.physical_start,end))
    if len(set(ids))!=len(ids): raise ValueError('context and resource IDs must be distinct')
    spans.sort()
    if any(r._overlap(a,b) for a,b in zip(spans,spans[1:])):
        raise ValueError('full resource allocations overlap, including unused padding')
    if type(events) is not tuple or len(events)>MAX_EVENTS:
        raise ValueError('bounded immutable claim trace required')
    by_id={a.allocation_id:a for a in resources}
    written={a.allocation_id:[] for a in resources}
    dirty={a.allocation_id:[] for a in resources}
    last_write={a.allocation_id:None for a in resources}
    code=next(a for a in resources if a.kind=='code');icache=[]
    fences=set();terminal=False;state='PREFIX';checkpoints=0
    def complete():
        return (all(_covers(written[a.allocation_id],(a.required_offset,a.required_offset+a.required_bytes)) for a in resources),
                all(not dirty[a.allocation_id] for a in resources),
                _covers(icache,_round((code.required_offset,code.required_offset+code.required_bytes),icache_line)))
    for ordinal,e in enumerate(events):
        if terminal: raise ValueError('terminal claims: no subsequent events/read/cleanup/retry')
        if (type(e) is not Event or type(e.kind) is not str or type(e.allocation_id) is not str or
                type(e.boot) is not str or type(e.attempt) is not str or e.boot!=boot or e.attempt!=attempt or
                type(e.offset) is not int or type(e.size) is not int or e.offset<0 or e.size<0):
            raise ValueError('typed same-context claim required')
        ranged=e.kind in ('write-claimed','poc-claimed','icache-claimed')
        if ranged:
            if e.allocation_id not in by_id or not e.size:
                raise ValueError('nonempty range of declared resource required')
            a=by_id[e.allocation_id];span=(e.offset,e.offset+e.size)
            if span[1]>a.allocated_bytes: raise ValueError('claim extends outside allocation')
            required=(a.required_offset,a.required_offset+a.required_bytes)
            if e.kind=='write-claimed':
                if not required[0]<=span[0]<span[1]<=required[1]:
                    raise ValueError('no implicit writes to allocation prefix/padding')
                written[a.allocation_id]=_union(written[a.allocation_id],span)
                dirty[a.allocation_id]=_union(dirty[a.allocation_id],_round(span,dcache_line))
                last_write[a.allocation_id]=ordinal
                if a.kind=='code': icache=[]
            elif e.kind=='poc-claimed':
                if span[0]%dcache_line or span[1]%dcache_line:
                    raise ValueError('PoC claim must cover complete assumed D-cache lines')
                dirty[a.allocation_id]=_subtract(dirty[a.allocation_id],span)
            else:
                if (a.kind!='code' or span[0]%icache_line or span[1]%icache_line or
                        not _covers(written[a.allocation_id],required) or dirty[a.allocation_id]):
                    raise ValueError('code initialized and PoC claimed before I-cache publication')
                icache=_union(icache,span)
        else:
            if e.allocation_id or e.offset or e.size: raise ValueError('non-range event shape required')
            if e.kind in UNKNOWN:
                state='FROZEN_UNKNOWN';terminal=True
            elif e.kind=='known-failure':
                state='FAILED_AFTER_IRREVERSIBLE' if fences.intersection(('no-inverse-attempt','global-shutdown')) else 'FAILED_RETAINED'
                terminal=True
            elif e.kind in FENCES:
                if e.kind in fences: raise ValueError('duplicate fixture boundary')
                fences.add(e.kind)
            elif e.kind=='observer-ack-claimed':
                if fences.intersection(('observer-frozen','transport-lost','no-inverse-attempt','global-shutdown')):
                    raise ValueError('no normal observer ACK assumed beyond relevant boundary')
            elif e.kind=='coverage-checkpoint':
                if not all(complete()): raise ValueError('missing initialization/PoC/I-cache coverage after latest writes')
                checkpoints+=1
            else: raise ValueError('unknown event; no dispatch/read/release/resume/entry operation')
    initialized,poc,code_published=complete()
    return dict(profile=PROFILE,scope='synthetic interval and event claims only; NOT physical publication or a helper',
        state=state,terminal=terminal,declared_fences=sorted(fences),coverage_checkpoints=checkpoints,
        required_bytes_written_claimed=initialized,no_dirty_dcache_lines_claimed=poc,
        code_icache_coverage_claimed=code_published,
        code_icache_intervals_claimed=[list(span) for span in icache],
        coverage_claims_complete=initialized and poc and code_published,
        resources=[dict(kind=a.kind,allocation_id=a.allocation_id,
            required_interval=[a.required_offset,a.required_offset+a.required_bytes],
            required_dcache_interval=list(_round((a.required_offset,a.required_offset+a.required_bytes),dcache_line)),
            written_intervals=[list(span) for span in written[a.allocation_id]],
            dirty_dcache_intervals=[list(span) for span in dirty[a.allocation_id]],
            last_write_event=last_write[a.allocation_id]) for a in resources],
        dcache_line_assumed=dcache_line,icache_line_assumed=icache_line,
        fixture_claims_are_runtime_evidence=False,cache_protocol_verified=False,
        authorization_verified=False,helper_implemented=False,**flags())
