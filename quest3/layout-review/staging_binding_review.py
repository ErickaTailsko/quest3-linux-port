#!/usr/bin/env python3
"""HOST-only composition of fixture geometry, phase claims and cache intervals.

No writer/helper/allocator/loader callbacks. Consistent claims are not actual
content/readback, authorization, ownership, cache maintenance or boot evidence.
"""
import cache_publication_plan as c
import direct_staging_trace as t
import returned_layout as r
from relocation_plan import flags

PROFILE='q3-staging-binding-review-host-v1'
MAX_STEPS=2048


def review(image,initrd,prepared_dtb,allocations,resources,steps,*,boot,attempt,
           buffer_bytes=r.PAGE,dcache_line=64,icache_line=64):
    """Review ONE ordered tuple of t.Event/c.Event claims, not two transcripts.

    Payload writes are derived as metadata only from phase copy/zero completions;
    caller-supplied payload write claims are forbidden. Code/table writes must
    precede seal. This deliberately restricted hypothesis requires global
    shutdown before cache claims, not an architecture-approved sequence.
    """
    layout=r.plan(image,initrd,prepared_dtb,allocations,attempt=attempt)
    if not layout['chosen_initrd_matches']: raise ValueError('prepared chosen required')
    c.review(resources,(),boot=boot,attempt=attempt,dcache_line=dcache_line,icache_line=icache_line)
    by_kind={a.kind:a for a in resources};slots={s['role']:s for s in layout['slots']}
    for role,slot in slots.items():
        a=by_kind[role]
        if (a.allocation_id!=slot['allocation_id'] or a.physical_start!=int(slot['allocation_start'],16) or
                a.allocated_bytes!=slot['allocation_bytes'] or
                a.required_offset!=int(slot['payload_start'],16)-a.physical_start or
                a.required_bytes!=slot['stage_bytes']):
            raise ValueError('payload resource does not bind exactly to returned layout')
    _,_,_,ram,fixed,_,_=r._dt(prepared_dtb)
    for a in resources:
        span=(a.physical_start,a.physical_start+a.allocated_bytes)
        if (not any(lo<=span[0] and span[1]<=hi for lo,hi in ram) or
                any(r._overlap(span,(lo,hi)) for lo,hi,_ in fixed)):
            raise ValueError('complete fixture resource outside supplied RAM or overlaps static reservation')
    if (type(steps) is not tuple or len(steps)>MAX_STEPS or
            any(type(e) not in (t.Event,c.Event) for e in steps)):
        raise ValueError('bounded single ordered tuple of typed phase/publication events required')
    segments=tuple(t.Segment(role,s['file_bytes'],s['stage_bytes']) for role,s in slots.items())
    phases=tuple(e for e in steps if type(e) is t.Event)
    phase_result=t.review(segments,phases,boot=boot,attempt=attempt,buffer_bytes=buffer_bytes)
    publication=[];state='NEW';terminal=False;ack=False;fences=set();links=[]
    def ledger():
        return c.review(resources,tuple(publication),boot=boot,attempt=attempt,
                        dcache_line=dcache_line,icache_line=icache_line)
    def marker(kind): return c.Event(kind,boot,attempt)
    for index,e in enumerate(steps):
        if terminal: raise ValueError('terminal bound trace: no later event or automatic cleanup')
        if type(e) is t.Event:
            if e.kind=='prepare': state='STAGING'
            elif e.kind in ('copy-complete','zero-complete'):
                a=by_kind[e.role]
                publication.append(c.Event('write-claimed',boot,attempt,a.allocation_id,
                                           a.required_offset+e.offset,e.amount))
                links.append(dict(step=index,publication_event=len(publication)-1,role=e.role,
                                  allocation_id=a.allocation_id,offset=a.required_offset+e.offset,size=e.amount))
            elif e.kind=='seal':
                if not ledger()['required_bytes_written_claimed']:
                    raise ValueError('initialize payload AND code/tables before seal')
                state='SEALED'
            elif e.kind=='irreversible-boundary':
                if not ack: raise ValueError('sealed-content observer checkpoint claim before boundary required')
                state='IRREVERSIBLE'
            elif e.kind=='final-clean':
                if 'global-shutdown' not in fences: raise ValueError('explicit global-shutdown claim required')
                publication.append(marker('coverage-checkpoint'))
                ledger()  # Exact range coverage at this phase, not merely at end.
                state='FINAL_CLEAN'
            elif e.kind=='entry-described':
                state='ENTRY_DESCRIBED';terminal=True
            if e.kind in t.UNCERTAIN+t.FAILURES or (e.kind=='read-complete' and not e.amount):
                publication.append(marker(e.kind if e.kind in c.UNKNOWN else 'known-failure'))
                terminal=True
        else:
            if e.kind=='write-claimed':
                if state!='STAGING' or e.allocation_id not in {by_kind[k].allocation_id for k in ('code','pgd','pud')}:
                    raise ValueError('only code/table initialization claims before seal; payload writes are derived')
            elif e.kind in ('poc-claimed','icache-claimed'):
                if state!='IRREVERSIBLE' or 'global-shutdown' not in fences:
                    raise ValueError('this hypothesis publishes only after explicit global shutdown and before final-clean')
            elif e.kind=='observer-ack-claimed':
                if state!='SEALED' or ack: raise ValueError('one ACK claim after seal, before loss/effects')
                ack=True
            elif e.kind in ('observer-frozen','transport-lost'):
                if state not in ('SEALED','IRREVERSIBLE'):
                    raise ValueError('observation-loss claims only after content seal')
                fences.add(e.kind)
            elif e.kind in ('no-inverse-attempt','global-shutdown'):
                if state!='IRREVERSIBLE' or (e.kind=='no-inverse-attempt' and 'global-shutdown' in fences):
                    raise ValueError('effect fence after phase boundary, no-inverse attempt before global shutdown')
                fences.add(e.kind)
            else:
                raise ValueError('publication lane has no independent failure/checkpoint/entry or dispatch API')
            publication.append(e)
    cache_result=ledger()
    complete=phase_result['full_entry_trace_described'] and cache_result['coverage_claims_complete'] and not cache_result['terminal']
    return dict(profile=PROFILE,scope='single HOST fixture consistency only; NOT runtime admission or physical evidence',
        input_sha256=layout['input_sha256'],dynamic_reservations_unresolved=layout['dynamic_reservation_locations_unresolved'],
        fixture_bindings_match=True,full_fixture_description=complete,phase=phase_result,publication=cache_result,
        derived_payload_write_links=links,
        fixture_claims_are_runtime_evidence=False,authorization_verified=False,
        target_readback_verified=False,cache_protocol_verified=False,helper_implemented=False,
        direct_writer_implemented=False,streaming_io_implemented=False,runtime_admission_enabled=False,**flags())
