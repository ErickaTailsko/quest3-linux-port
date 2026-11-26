#!/usr/bin/env python3
"""Pure HOST claim-trace review; NOT a writer, controller or recovery API.

Events assert fictitious completions. No bytes, mappings, handles, cache ops or
authorization are verified. Replaying a trace does not establish live resources.
"""
from dataclasses import dataclass

import returned_layout as r
from relocation_plan import flags

PROFILE='q3-direct-staging-trace-host-v1'
MAX_EVENTS=65536
PREPARE_CLAIMS=(
    'specific-write-consent','current-boot-and-stable-inputs',
    'real-handles-retained-including-transition','default-cma-identity-and-lifetime',
    'layout-chosen-and-full-range-alias-review','writable-mappings-and-attributes',
    'writer-dma-exclusion','bounded-buffer-and-io-available','failure-and-log-contract',
)
SEAL_CLAIMS=('source-digests-match','destination-bytes-and-zeros-match',
             'no-inflight-access','content-frozen-and-handles-retained')
SHUTDOWN_CLAIMS=('cpu-dma-smmu-watchdog-qmp-reviewed','cfi-scs-entry-reviewed',
                 'last-recoverable-checkpoint','irreversible-boundary-reviewed')
CLEAN_CLAIMS=('destinations-clean-to-poc-after-last-write','cache-lines-within-owned-ranges',
              'transition-data-code-icache-published','barriers-mmu-entry-reviewed')
UNCERTAIN=('timeout','interrupted','journal-failed','completion-unknown','restart')
FAILURES=('io-error','content-mismatch','mapping-changed','handle-lost',
          'external-writer','release-failed')


@dataclass(frozen=True)
class Segment:
    role: str
    file_bytes: int
    stage_bytes: int


@dataclass(frozen=True)
class Event:
    kind: str
    boot: str
    attempt: str
    role: str = ''
    offset: int = 0
    amount: int = 0
    claims: tuple = ()


def review(segments,events,*,boot,attempt,buffer_bytes=r.PAGE):
    """Review a bounded complete HOST trace, never dispatch its event names.

    Offsets are relative to each payload, NOT physical addresses. Prefix/padding
    outside stage_bytes is never included. Only one claimed read/buffer may be
    outstanding globally. Known failures and uncertainty are terminal; there is
    deliberately no cleanup, retry, fallback, resume or actual entry operation.
    """
    r._nonce(boot);r._nonce(attempt)
    if boot==attempt: raise ValueError('distinct fixture boot/attempt required')
    if type(buffer_bytes) is not int or not r.PAGE<=buffer_bytes<=r.ALIGN or buffer_bytes%r.PAGE:
        raise ValueError('bounded page-aligned buffer required')
    if (type(segments) is not tuple or len(segments)!=3 or
            any(type(s) is not Segment or type(s.role) is not str or s.role not in r.PROVIDERS or
                type(s.file_bytes) is not int or type(s.stage_bytes) is not int or
                not 0<s.file_bytes<=s.stage_bytes or s.stage_bytes%r.PAGE or
                s.stage_bytes>(32*r.MIB if s.role=='image' else r.ALIGN) for s in segments) or
            {s.role for s in segments}!=set(r.PROVIDERS)):
        raise ValueError('three bounded typed segment geometries required')
    if type(events) is not tuple or len(events)>MAX_EVENTS:
        raise ValueError('bounded immutable event tuple required')
    sizes={s.role:s for s in segments}
    copied={s.role:0 for s in segments};zeroed={s.role:0 for s in segments}
    state='NEW';pending=None;terminal=False;irreversible=False
    def claims_match(event,expected):
        if len(event.claims)!=len(expected) or set(event.claims)!=set(expected):
            raise ValueError('exact phase-specific fixture claims required')
    for e in events:
        if terminal: raise ValueError('terminal trace: no further commands, reads or cleanup')
        if (type(e) is not Event or type(e.kind) is not str or type(e.role) is not str or
                type(e.offset) is not int or type(e.amount) is not int or e.offset<0 or e.amount<0 or
                type(e.claims) is not tuple or any(type(c) is not str for c in e.claims) or
                type(e.boot) is not str or type(e.attempt) is not str or e.boot!=boot or e.attempt!=attempt):
            raise ValueError('typed same-context fixture event required')
        data_event=e.kind in ('read-request','read-complete','copy-complete','zero-complete')
        if data_event:
            if e.role not in sizes or e.claims: raise ValueError('segment event shape required')
        elif e.role or e.offset or e.amount:
            raise ValueError('phase/failure events have no ranges')
        if e.kind in UNCERTAIN+FAILURES:
            claims_match(e,())
            state=('FROZEN_UNKNOWN' if e.kind in UNCERTAIN else
                   'FAILED_AFTER_IRREVERSIBLE' if irreversible else 'FAILED_RETAINED')
            terminal=True
        elif e.kind=='prepare':
            if state!='NEW': raise ValueError('one preparation only')
            claims_match(e,PREPARE_CLAIMS);state='STAGING'
        elif data_event:
            if state!='STAGING': raise ValueError('no staging before preparation or after sealing')
            s=sizes[e.role]
            if e.kind=='read-request':
                if (pending is not None or e.offset!=copied[e.role] or
                        not 0<e.amount<=min(buffer_bytes,s.file_bytes-e.offset)):
                    raise ValueError('one bounded in-order read, no buffer reuse')
                pending=('read',e.role,e.offset,e.amount)
            elif e.kind=='read-complete':
                if (pending is None or pending[:3]!=('read',e.role,e.offset) or e.amount>pending[3]):
                    raise ValueError('completion must match outstanding request')
                if not e.amount:
                    pending=None;state='FAILED_RETAINED';terminal=True  # Completed read, premature EOF.
                else: pending=('buffer',e.role,e.offset,e.amount)
            elif e.kind=='copy-complete':
                if pending!=('buffer',e.role,e.offset,e.amount):
                    raise ValueError('only exact completed buffer bytes may be claimed copied')
                copied[e.role]+=e.amount;pending=None
            else:
                if (pending is not None or copied[e.role]!=s.file_bytes or
                        e.offset!=s.file_bytes+zeroed[e.role] or
                        not 0<e.amount<=min(buffer_bytes,s.stage_bytes-e.offset)):
                    raise ValueError('bounded in-order zero fill only after file completion')
                zeroed[e.role]+=e.amount
        elif e.kind=='seal':
            if (state!='STAGING' or pending is not None or
                    any(copied[s.role]!=s.file_bytes or zeroed[s.role]!=s.stage_bytes-s.file_bytes for s in segments)):
                raise ValueError('all file bytes/zeros and I/O completion required')
            claims_match(e,SEAL_CLAIMS);state='SEALED'
        elif e.kind=='irreversible-boundary':
            if state!='SEALED': raise ValueError('seal before irreversible effects')
            claims_match(e,SHUTDOWN_CLAIMS);state='IRREVERSIBLE';irreversible=True
        elif e.kind=='final-clean':
            if state!='IRREVERSIBLE': raise ValueError('this fixture orders final clean after boundary')
            claims_match(e,CLEAN_CLAIMS);state='CLEAN_CLAIMED'
        elif e.kind=='entry-described':
            if state!='CLEAN_CLAIMED': raise ValueError('final publication claims required')
            claims_match(e,('dedicated-no-copy-path-reviewed',));state='ENTRY_DESCRIBED';terminal=True
        else:
            raise ValueError('unknown event; no cleanup/retry/fallback/resume API')
    return dict(profile=PROFILE,scope='host fixture claims only; NOT proof of execution, content or resources',
        state=state,trace_prefix_accepted=True,full_entry_trace_described=state=='ENTRY_DESCRIBED',
        copied_bytes_claimed=copied,zeroed_bytes_claimed=zeroed,
        pending_read_claimed=pending is not None and pending[0]=='read',
        buffer_bytes_pending_copy_claimed=pending[3] if pending is not None and pending[0]=='buffer' else 0,
        terminal=terminal,
        irreversible_boundary_claimed=irreversible,
        fixture_claims_are_runtime_evidence=False,cache_protocol_verified=False,
        target_readback_verified=False,authorization_verified=False,direct_writer_implemented=False,
        streaming_io_implemented=False,**flags())
