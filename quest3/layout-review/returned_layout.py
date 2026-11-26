#!/usr/bin/env python3
"""Pure HOST fixture layout for separately supplied allocator-result records.

No allocator, PFN probing, ownership import, copy, release, loader or transport.
Labels/tokens are data, NOT proof of ownership, default CMA identity or lifetime.
"""
from dataclasses import dataclass
import hashlib
import re
import struct

from fdtcheck import read, rewrite

PAGE=4096
MIB=1024*1024
GIB=1024*MIB
ALIGN=2*MIB
PHYS_LIMIT=1<<48  # Reviewed candidate PA_BITS=48; not runtime PA validation.
PROFILE='q3-returned-layout-host-v1'
PROVIDERS={'image':'default-cma-image','initrd':'buddy-initrd','dtb':'buddy-dtb'}


@dataclass(frozen=True)
class Allocation:
    role: str
    provider: str
    allocation_id: str
    attempt: str
    physical_start: int
    allocated_bytes: int
    provenance: str = 'host-fixture-only'


@dataclass(frozen=True)
class Exclusion:
    label: str
    physical_start: int
    size_bytes: int


def _nonce(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):
        raise ValueError('typed fixture nonce required')
    return value


def _end(start,size):
    if (type(start) is not int or type(size) is not int or not 0<=start<PHYS_LIMIT or
            not 0<size<=PHYS_LIMIT-start):
        raise ValueError('physical range type/zero/overflow/PA bound mismatch')
    return start+size


def _up(value,alignment): return (value+alignment-1)//alignment*alignment


def _overlap(a,b): return a[0]<b[1] and b[0]<a[1]


def _dt(blob):
    if not isinstance(blob,bytes) or not 40<=len(blob)<=ALIGN:
        raise ValueError('DTB outside reviewed 2 MiB capacity')
    header=struct.unpack_from('>10I',blob)
    if header[0]!=0xd00dfeed or header[1]!=len(blob): raise ValueError('DTB magic/total size mismatch')
    nodes,reserved,cpu=read(blob)
    _,_,offstruct,offstrings,offreserve,_,_,_,stringsize,structsize=header
    sections=[(offstruct,offstruct+structsize),(offstrings,offstrings+stringsize),
              (offreserve,offreserve+16*(len(reserved)+1))]
    if (offstruct%4 or offreserve%8 or any(not 40<=lo<hi<=len(blob) for lo,hi in sections) or
            any(_overlap(a,b) for i,a in enumerate(sections) for b in sections[i+1:])):
        raise ValueError('DTB sections overlap or have unsupported alignment')
    root=nodes['/'];compat=root.get('compatible',b'').split(b'\0')
    cells=struct.pack('>I',2)
    if (b'qcom,anorak' not in compat or b'oculus,eureka' not in compat or
            root.get('#address-cells')!=cells or root.get('#size-cells')!=cells or '/chosen' not in nodes):
        raise ValueError('unsupported Quest 3 board/addressing/chosen')
    ram=[];fixed=[];dynamic=[];zero_ram=0
    for address,size in reserved: fixed.append((address,_end(address,size),'fdt-memreserve'))
    def pairs(data,allow_empty_extent=False):
        if not data or len(data)%16: raise ValueError('unsupported DT 64-bit reg pairs')
        result=[]
        for a,n in struct.iter_unpack('>QQ',data):
            if not n and allow_empty_extent:
                if a>=PHYS_LIMIT: raise ValueError('empty RAM entry outside PA profile')
                continue
            result.append((a,_end(a,n)))
        return result
    for path,props in nodes.items():
        if path.count('/')==1 and props.get('device_type')==b'memory\0':
            data=props.get('reg',b'')
            ram.extend(pairs(data,True))
            zero_ram+=sum(n==0 for _,n in struct.iter_unpack('>QQ',data))
    if not ram: raise ValueError('DT has no reviewed root-level memory extents')
    ram.sort()
    if any(_overlap(a,b) for a,b in zip(ram,ram[1:])): raise ValueError('ambiguous overlapping DT memory extents')
    r=nodes.get('/reserved-memory')
    if r is None or r.get('#address-cells')!=cells or r.get('#size-cells')!=cells or r.get('ranges')!=b'':
        raise ValueError('unsupported reserved-memory addressing')
    for path,props in nodes.items():
        if not path.startswith('/reserved-memory/'): continue
        if path.count('/')!=2: raise ValueError('nested reserved-memory translation is not reviewed')
        if props.get('reg'):
            fixed.extend((a,e,path) for a,e in pairs(props['reg']))
        elif 'size' in props:
            if len(props['size'])!=8 or not struct.unpack('>Q',props['size'])[0]:
                raise ValueError('invalid dynamic reservation size')
            if 'alloc-ranges' in props:
                # Search constraints may span the u64 domain. They are NOT
                # returned allocations and must not be treated as PA48 RAM.
                constraints=props['alloc-ranges']
                if (not constraints or len(constraints)%16 or
                        any(not n or n>(1<<64)-a for a,n in struct.iter_unpack('>QQ',constraints))):
                    raise ValueError('invalid dynamic allocation constraints')
            dynamic.append(path)  # Never infer a location or clearance from this.
        else: dynamic.append(path)
    return nodes,reserved,cpu,ram,fixed,sorted(dynamic),zero_ram


def plan(image,initrd,dtb,allocations,*,attempt,extra_exclusions=()):
    """Check supplied SYNTHETIC addresses; never choose/acquire a destination."""
    _nonce(attempt)
    if not isinstance(image,bytes) or len(image)<64 or image[56:60]!=b'ARM\x64':
        raise ValueError('raw ARM64 Image required')
    offset,size,flags=struct.unpack_from('<QQQ',image,8)
    if offset not in (0,0x80000) or not len(image)<=size<=32*MIB or flags not in (8,10):
        raise ValueError('Image outside reviewed offset/size/LE/4K/placement profile')
    image_stage=_up(size,PAGE);image_request=_up(offset+image_stage,ALIGN)
    if image_request>32*MIB: raise ValueError('Image request exceeds reviewed 32 MiB route')
    if not isinstance(initrd,bytes) or not 0<len(initrd)<=ALIGN:
        raise ValueError('initrd outside reviewed separate-slot capacity')
    nodes,_,_,ram,fixed,dynamic,zero_ram=_dt(dtb)
    if (not isinstance(allocations,(list,tuple)) or len(allocations)!=3 or
            any(type(a) is not Allocation or type(a.role) is not str or type(a.provider) is not str
                for a in allocations)):
        raise ValueError('exactly three typed fixture allocation results required')
    by_role={a.role:a for a in allocations}
    if set(by_role)!=set(PROVIDERS): raise ValueError('one distinct allocation per role required')
    ids=[_nonce(a.allocation_id) for a in allocations]
    if len(set([attempt,*ids]))!=4: raise ValueError('allocation/attempt IDs must be distinct')
    ranges={}
    for role,a in by_role.items():
        _nonce(a.attempt)
        required=image_request if role=='image' else ALIGN
        if (a.provider!=PROVIDERS[role] or a.attempt!=attempt or a.provenance!='host-fixture-only' or
                type(a.allocated_bytes) is not int or a.allocated_bytes!=required or
                type(a.physical_start) is not int or not a.physical_start or a.physical_start%ALIGN):
            raise ValueError('provider/context/provenance/size/alignment mismatch')
        end=_end(a.physical_start,a.allocated_bytes);ranges[role]=(a.physical_start,end)
        if not any(lo<=a.physical_start and end<=hi for lo,hi in ram):
            raise ValueError('complete allocation not covered by one supplied DT RAM extent')
    for i,role in enumerate(PROVIDERS):
        if any(_overlap(ranges[role],ranges[other]) for other in list(PROVIDERS)[i+1:]):
            raise ValueError('allocation slots overlap, including padding')
    if not isinstance(extra_exclusions,(list,tuple)) or len(extra_exclusions)>256:
        raise ValueError('bounded explicit extra exclusions required')
    for e in extra_exclusions:
        if type(e) is not Exclusion or not isinstance(e.label,str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',e.label):
            raise ValueError('typed exclusion label/range required')
        fixed.append((e.physical_start,_end(e.physical_start,e.size_bytes),e.label))
    for role,span in ranges.items():
        if any(_overlap(span,(lo,hi)) for lo,hi,_ in fixed):
            raise ValueError('allocation intersects a supplied/static exclusion: '+role)
    entry=ranges['image'][0]+offset;initrd_start=ranges['initrd'][0]
    required_end=max(entry+image_stage,initrd_start+_up(len(initrd),PAGE))
    window_start=min(entry,initrd_start)//GIB*GIB
    window_size=_up(required_end-window_start,GIB)
    if window_size>32*GIB: raise ValueError('Image/initrd cannot share the ARM64 1GiB-aligned <=32GiB window')
    window_end=_end(window_start,window_size)
    chosen={'linux,initrd-start':initrd_start,'linux,initrd-end':initrd_start+len(initrd)}
    chosen_matches=all(nodes['/chosen'].get(name)==struct.pack('>Q',value) for name,value in chosen.items())
    slots=[]
    for role,payload,stage,start in (('image',image,image_stage,entry),
            ('initrd',initrd,_up(len(initrd),PAGE),initrd_start),
            ('dtb',dtb,_up(len(dtb),PAGE),ranges['dtb'][0])):
        end=_end(start,stage)
        if start<ranges[role][0] or end>ranges[role][1]: raise ValueError('page-rounded stage exceeds its allocation')
        a=by_role[role]
        slots.append(dict(role=role,provider_label=a.provider,allocation_id=a.allocation_id,
            allocation_start=hex(ranges[role][0]),allocation_end_exclusive=hex(ranges[role][1]),
            allocation_bytes=a.allocated_bytes,payload_start=hex(start),file_bytes=len(payload),
            file_end_exclusive=hex(start+len(payload)),stage_bytes=stage,stage_end_exclusive=hex(end),
            zero_tail_bytes=stage-len(payload),copy_pages=stage//PAGE))
    return dict(profile=PROFILE,scope='supplied synthetic allocation geometry only; no ownership or placement approval',
        attempt=attempt,slots=slots,image_text_offset=hex(offset),image_effective_bytes=size,
        total_request_bytes=sum(a.allocated_bytes for a in allocations),combined_contiguous_window_required=False,
        arm64_initrd_window=dict(start=hex(window_start),end_exclusive=hex(window_end),bytes=window_size),
        handoff_data_only=dict(entry=hex(entry),x0_dtb=hex(ranges['dtb'][0]),x1=0,x2=0,x3=0),
        chosen_initrd_expected={key:hex(value) for key,value in chosen.items()},chosen_initrd_matches=chosen_matches,
        supplied_slots_inside_dtb_ram_geometrically=True,static_exclusions_checked=len(fixed),
        zero_length_memory_entries_ignored=zero_ram,
        dynamic_reservation_locations_unresolved=dynamic,
        input_sha256={name:hashlib.sha256(blob).hexdigest() for name,blob in (('image',image),('initrd',initrd),('dtb',dtb))},
        execution_enabled=False,allocator_call_authorized=False,allocator_called=False,
        runtime_allocator_results_verified=False,default_cma_runtime_identity_verified=False,
        default_pool_available_capacity_proven=False,allocation_lifetime_verified=False,
        dedicated_pool_borrowing_allowed=False,ownership_acquired=False,all_pfns_validated=False,
        current_boot_layout_validated=False,dt_mapping_attributes_verified=False,
        all_reservations_located=False,dma_safety_proven=False,source_and_scratch_pages_checked=False,
        loader_integrated=False,new_physical_base_selected=False,cleanup_permitted=False,
        bootargs_reviewed=False,handoff_architecture_verified=False,boot_ready=False)


def prepare_dtb(image,initrd,dtb,allocations,*,attempt,extra_exclusions=()):
    """Return a NEW host DTB byte string; mutate only chosen initrd semantics."""
    report=plan(image,initrd,dtb,allocations,attempt=attempt,extra_exclusions=extra_exclusions)
    changes={('/chosen',name):struct.pack('>Q',int(value,16))
             for name,value in report['chosen_initrd_expected'].items()}
    before,reservations,cpu=read(dtb)
    prepared=rewrite(dtb,changes)
    after,new_reservations,new_cpu=read(prepared)
    if set(before)!=set(after) or reservations!=new_reservations or cpu!=new_cpu:
        raise ValueError('unexpected DT nodes/reservations/boot CPU change')
    for path,props in before.items():
        for name in props.keys()|after[path].keys():
            if after[path].get(name)!=changes.get((path,name),props.get(name)):
                raise ValueError('unexpected property change outside chosen initrd addresses')
    result=plan(image,initrd,prepared,allocations,attempt=attempt,extra_exclusions=extra_exclusions)
    if not result['chosen_initrd_matches']: raise ValueError('prepared chosen mismatch')
    result.update(original_dtb_sha256=hashlib.sha256(dtb).hexdigest(),
                  only_chosen_initrd_properties_changed_semantically=True)
    return prepared,result
