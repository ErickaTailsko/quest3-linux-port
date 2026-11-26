#!/usr/bin/env python3
"""HOST snapshots/descriptor model. No allocator, physical read/write or handoff.

Resource tokens, snapshots and 'retained' comparisons are fixture metadata, NOT
kernel handles or evidence that real pages remain allocated. Binary descriptors
are never supplied to the active loader by this library.
"""
from dataclasses import dataclass
import hashlib
import json
import struct

import returned_layout as r

PROFILE='q3-relocation-plan-host-v1'
DESCRIPTOR_CAPACITY=(r.PAGE-16)//16
MAX_WORK_PAGES=32768
MAX_SCRATCH=16
KINDS=('source','descriptor','relocation-code','pgd','pud','scratch')
ZERO_PAGE=bytes(r.PAGE)


@dataclass(frozen=True)
class Page:
    kind: str
    allocation_id: str
    attempt: str
    physical_start: int
    index: int = 0
    role: str = ''
    contents: bytes = b''
    provenance: str = 'host-fixture-only'


@dataclass(frozen=True)
class Copy:
    role: str
    index: int
    allocation_id: str
    source: int
    destination: int
    source_sha256: str
    file_bytes: int
    zero_bytes: int


@dataclass(frozen=True)
class Descriptor:
    allocation_id: str
    physical_start: int
    contents: bytes


@dataclass(frozen=True)
class Plan:
    attempt: str
    allocations: tuple
    pages: tuple
    copies: tuple
    descriptors: tuple
    payload_sha256: tuple
    image_entry: int
    dtb_address: int
    retained_records_sha256: str
    dynamic_reservations_unresolved: tuple = ()
    profile: str = PROFILE


def flags():
    return dict(execution_enabled=False,allocator_called=False,
        runtime_allocator_results_verified=False,ownership_acquired=False,
        all_pfns_validated=False,current_boot_layout_validated=False,
        allocation_lifetime_verified=False,all_reservations_located=False,
        actual_handles_live_verified=False,source_snapshots_are_physical_readback=False,
        payload_written_to_target=False,descriptors_written_to_target=False,
        page_tables_built=False,relocation_code_verified=False,cfi_handoff_verified=False,
        dma_safety_proven=False,loader_integrated=False,cleanup_permitted=False,
        runtime_memory_impact_proven=False,
        automatic_resume_allowed=False,boot_ready=False)


def _canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')


def _page_key(page): return (page.kind,page.role,page.index,page.allocation_id)


def _pages(pages,attempt):
    if not isinstance(pages,(list,tuple)) or not 1<=len(pages)<=MAX_WORK_PAGES:
        raise ValueError('bounded typed work-page records required')
    for page in pages:
        if (type(page) is not Page or type(page.kind) is not str or page.kind not in KINDS or
                type(page.role) is not str or type(page.index) is not int or
                not 0<=page.index<MAX_WORK_PAGES or page.provenance!='host-fixture-only' or
                type(page.physical_start) is not int or not page.physical_start or page.physical_start%r.PAGE or
                type(page.contents) is not bytes):
            raise ValueError('invalid work-page type/role/index/provenance/alignment')
        r._nonce(page.allocation_id);r._nonce(page.attempt)
        if page.attempt!=attempt: raise ValueError('mixed work-page attempt')
        r._end(page.physical_start,r.PAGE)
        if page.kind=='source':
            if page.role not in r.PROVIDERS or len(page.contents)!=r.PAGE:
                raise ValueError('source role and exact immutable page snapshot required')
        elif page.role or page.contents or (page.kind in ('relocation-code','pgd','pud') and page.index!=0):
            raise ValueError('auxiliary records are geometry only, not code/table snapshots')
    return tuple(sorted(pages,key=_page_key))


def _ledger(allocations,pages,attempt):
    if (not isinstance(allocations,(list,tuple)) or len(allocations)!=3 or
            any(type(a) is not r.Allocation for a in allocations)):
        raise ValueError('three typed destination records required')
    rows=[]
    for a in allocations:
        if (type(a.role) is not str or a.role not in r.PROVIDERS or type(a.provider) is not str or
                a.provider!=r.PROVIDERS[a.role] or a.provenance!='host-fixture-only' or a.attempt!=attempt):
            raise ValueError('destination metadata/context changed')
        r._nonce(a.allocation_id);r._nonce(a.attempt);r._end(a.physical_start,a.allocated_bytes)
        rows.append(dict(role=a.role,provider=a.provider,id=a.allocation_id,attempt=a.attempt,
                         start=a.physical_start,bytes=a.allocated_bytes,provenance=a.provenance))
    if len({row['role'] for row in rows})!=3: raise ValueError('duplicate destination role')
    records=[dict(kind=p.kind,role=p.role,index=p.index,id=p.allocation_id,attempt=p.attempt,
        start=p.physical_start,provenance=p.provenance,contents_sha256=hashlib.sha256(p.contents).hexdigest()) for p in pages]
    ids=[attempt]+[row['id'] for row in rows]+[p.allocation_id for p in pages]
    if len(set(ids))!=len(ids): raise ValueError('destination/work/attempt IDs must all be distinct')
    return hashlib.sha256(b'ERIS-Q3-RETAINED-FIXTURE-RECORDS-V1\0'+_canonical(dict(
        attempt=attempt,destinations=sorted(rows,key=lambda row:row['role']),pages=records))).hexdigest()


def expected_source_page(payload,index):
    """Construct host bytes only; this does not initialize any physical page."""
    if type(payload) is not bytes or type(index) is not int or not 0<=index<MAX_WORK_PAGES:
        raise ValueError('bounded payload/page index required')
    start=index*r.PAGE
    return payload[start:start+r.PAGE].ljust(r.PAGE,b'\0') if start<len(payload) else ZERO_PAGE


def build(image,initrd,prepared_dtb,allocations,pages,*,attempt):
    layout=r.plan(image,initrd,prepared_dtb,allocations,attempt=attempt)
    if not layout['chosen_initrd_matches']: raise ValueError('prepare chosen initrd addresses BEFORE staging')
    ordered=_pages(pages,attempt);ledger=_ledger(allocations,ordered,attempt)
    destinations=[(int(slot['allocation_start'],16),int(slot['allocation_end_exclusive'],16)) for slot in layout['slots']]
    physical=sorted((p.physical_start,r._end(p.physical_start,r.PAGE)) for p in ordered)
    _,_,_,ram,fixed,_,_=r._dt(prepared_dtb)
    if any(not any(lo<=start and end<=hi for lo,hi in ram) for start,end in physical):
        raise ValueError('work page outside one supplied DT RAM extent')
    if any(r._overlap(span,(lo,hi)) for span in physical for lo,hi,_ in fixed):
        raise ValueError('work page overlaps a supplied static DT reservation')
    if any(r._overlap(a,b) for a,b in zip(physical,physical[1:])):
        raise ValueError('work pages alias each other: source/descriptor/code/tables/scratch')
    if any(r._overlap(span,dest) for span in physical for dest in destinations):
        raise ValueError('work page intersects a FULL destination allocation, including padding')
    sources={};descriptor_pages={};aux={kind:[] for kind in KINDS if kind not in ('source','descriptor')}
    for page in ordered:
        if page.kind=='source':
            key=(page.role,page.index)
            if key in sources: raise ValueError('duplicate source role/index')
            sources[key]=page
        elif page.kind=='descriptor':
            if page.index in descriptor_pages: raise ValueError('duplicate descriptor index')
            descriptor_pages[page.index]=page
        else: aux[page.kind].append(page)
    if any(len(aux[kind])!=1 for kind in ('relocation-code','pgd','pud')):
        raise ValueError('exactly one code/PGD/PUD metadata record required')
    if (len(aux['scratch'])>MAX_SCRATCH or
            {p.index for p in aux['scratch']}!=set(range(len(aux['scratch'])))):
        raise ValueError('bounded contiguous scratch indices required')
    copies=[];payloads={'image':image,'initrd':initrd,'dtb':prepared_dtb};expected_keys=set()
    for slot in layout['slots']:
        role=slot['role'];payload=payloads[role];start=int(slot['payload_start'],16)
        for index in range(slot['copy_pages']):
            key=(role,index);expected_keys.add(key)
            if key not in sources: raise ValueError('missing staged source page')
            page=sources[key];expected=expected_source_page(payload,index)
            if page.contents!=expected: raise ValueError('source snapshot differs from file bytes/page-rounded zero fill')
            file_bytes=min(r.PAGE,max(0,len(payload)-index*r.PAGE))
            copies.append(Copy(role,index,page.allocation_id,page.physical_start,start+index*r.PAGE,
                hashlib.sha256(expected).hexdigest(),file_bytes,r.PAGE-file_bytes))
    if set(sources)!=expected_keys: raise ValueError('extra/out-of-range staged source page')
    count=(len(copies)+DESCRIPTOR_CAPACITY-1)//DESCRIPTOR_CAPACITY
    if set(descriptor_pages)!=set(range(count)): raise ValueError('exact descriptor capacity/indices required')
    descriptors=[]
    for index in range(count):
        page=descriptor_pages[index];chunk=copies[index*DESCRIPTOR_CAPACITY:(index+1)*DESCRIPTOR_CAPACITY]
        next_address=descriptor_pages[index+1].physical_start if index+1<count else 0
        data=bytearray(r.PAGE);struct.pack_into('<QQ',data,0,next_address,len(chunk))
        for n,copy in enumerate(chunk): struct.pack_into('<QQ',data,16+n*16,copy.source,copy.destination)
        descriptors.append(Descriptor(page.allocation_id,page.physical_start,bytes(data)))
    result=Plan(attempt,tuple(sorted(allocations,key=lambda a:a.role)),ordered,tuple(copies),tuple(descriptors),
        tuple(sorted(layout['input_sha256'].items())),int(layout['handoff_data_only']['entry'],16),
        int(layout['handoff_data_only']['x0_dtb'],16),ledger,
        dynamic_reservations_unresolved=tuple(layout['dynamic_reservation_locations_unresolved']))
    validate_descriptor_chain(result,result.descriptors)
    return result


def validate_descriptor_chain(plan,descriptors):
    """Parse only supplied HOST byte strings; never follow a physical pointer."""
    if (type(plan) is not Plan or plan.profile!=PROFILE or not 1<=len(plan.copies)<=MAX_WORK_PAGES or
            not isinstance(descriptors,(list,tuple)) or len(descriptors)!=len(plan.descriptors) or
            len(descriptors)!=(len(plan.copies)+DESCRIPTOR_CAPACITY-1)//DESCRIPTOR_CAPACITY):
        raise ValueError('bounded plan/descriptor set required')
    expected={(d.allocation_id,d.physical_start) for d in plan.descriptors}
    if any(type(d) is not Descriptor or type(d.contents) is not bytes or len(d.contents)!=r.PAGE for d in descriptors):
        raise ValueError('exact immutable descriptor pages required')
    for d in descriptors:
        r._nonce(d.allocation_id)
        if type(d.physical_start) is not int or not d.physical_start or d.physical_start%r.PAGE:
            raise ValueError('descriptor page physical alignment mismatch')
        r._end(d.physical_start,r.PAGE)
    if ({(d.allocation_id,d.physical_start) for d in descriptors}!=expected or
            len({d.physical_start for d in descriptors})!=len(descriptors)):
        raise ValueError('descriptor metadata missing/aliased/substituted')
    by_address={d.physical_start:d for d in descriptors};address=plan.descriptors[0].physical_start
    seen=set();ordinal=0;copied=0
    while address:
        if address in seen or address not in by_address or ordinal>=len(plan.descriptors):
            raise ValueError('cycle/foreign descriptor link')
        seen.add(address);data=by_address[address].contents
        next_address,count=struct.unpack_from('<QQ',data)
        chunk=plan.copies[copied:copied+DESCRIPTOR_CAPACITY]
        expected_next=plan.descriptors[ordinal+1].physical_start if ordinal+1<len(plan.descriptors) else 0
        if count!=len(chunk) or not 1<=count<=DESCRIPTOR_CAPACITY or next_address!=expected_next:
            raise ValueError('descriptor count/order/termination mismatch')
        for index,copy in enumerate(chunk):
            if struct.unpack_from('<QQ',data,16+index*16)!=(copy.source,copy.destination):
                raise ValueError('descriptor source/destination/order mismatch')
        if any(data[16+count*16:]): raise ValueError('nonzero unused descriptor entries/tail')
        copied+=count;ordinal+=1;address=next_address
    if copied!=len(plan.copies) or len(seen)!=len(descriptors): raise ValueError('truncated/unreachable descriptor chain')
    return dict(profile=PROFILE,supplied_descriptor_chain_matches=True,
                copy_pages=copied,descriptor_pages=len(descriptors),**flags())


def review_retained_records(plan,allocations,pages):
    """Compare supplied fixture metadata/snapshots, NOT actual page liveness."""
    if type(plan) is not Plan or plan.profile!=PROFILE: raise ValueError('typed host plan required')
    ordered=_pages(pages,plan.attempt)
    if _ledger(allocations,ordered,plan.attempt)!=plan.retained_records_sha256:
        raise ValueError('retained fixture metadata/snapshots differ; no automatic cleanup/retry')
    return dict(profile=PROFILE,supplied_retained_records_match=True,**flags())


def summary(plan):
    if type(plan) is not Plan or plan.profile!=PROFILE: raise ValueError('typed host plan required')
    return dict(profile=PROFILE,scope='host fixture snapshots and descriptors only; NOT executable or owned memory',
        attempt=plan.attempt,source_pages=len(plan.copies),descriptor_pages=len(plan.descriptors),
        auxiliary_pages=sum(p.kind not in ('source','descriptor') for p in plan.pages),
        total_work_pages=len(plan.pages),descriptor_capacity=DESCRIPTOR_CAPACITY,
        destination_requested_bytes=sum(a.allocated_bytes for a in plan.allocations),
        source_staging_bytes=len(plan.copies)*r.PAGE,descriptor_bytes=len(plan.descriptors)*r.PAGE,
        work_page_bytes=len(plan.pages)*r.PAGE,
        modeled_retained_bytes=sum(a.allocated_bytes for a in plan.allocations)+len(plan.pages)*r.PAGE,
        page_cache_and_rejected_pages_included=False,
        copy_pages_by_role={role:sum(copy.role==role for copy in plan.copies) for role in r.PROVIDERS},
        image_entry=hex(plan.image_entry),dtb_address=hex(plan.dtb_address),
        retained_records_sha256=plan.retained_records_sha256,payload_sha256=dict(plan.payload_sha256),
        dynamic_reservations_unresolved=list(plan.dynamic_reservations_unresolved),
        supplied_work_geometry_checked=True,source_snapshot_bytes_match=True,**flags())
