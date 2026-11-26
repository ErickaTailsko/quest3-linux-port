#!/usr/bin/env python3
"""Supplied allocation geometry only; fictitious RAM/addresses, never providers."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct

import returned_layout as r
from fdtcheck import read, rewrite

BASE=64*r.GIB  # Deliberately fictitious Quest RAM; NOT a proposed device base.
ATTEMPT='a'*32


def dtb(*,memory=None,static=(),memreserve=(),dynamic=True,chosen=True,padding=None):
    strings=bytearray();offsets={};tokens=bytearray()
    def word(value): tokens.extend(struct.pack('>I',value))
    def begin(name):
        word(1);tokens.extend(name.encode()+b'\0');tokens.extend(b'\0'*(-len(tokens)%4))
    def prop(name,value):
        if name not in offsets: offsets[name]=len(strings);strings.extend(name.encode()+b'\0')
        tokens.extend(struct.pack('>III',3,len(value),offsets[name]));tokens.extend(value)
        tokens.extend(b'\0'*(-len(tokens)%4))
    begin('');prop('compatible',b'qcom,anorak\0oculus,eureka\0')
    prop('#address-cells',struct.pack('>I',2));prop('#size-cells',struct.pack('>I',2))
    if padding is not None: prop('fixture-padding',padding)
    begin('memory@fixture');prop('device_type',b'memory\0')
    prop('reg',b''.join(struct.pack('>QQ',start,size) for start,size in
        (memory if memory is not None else [(BASE-4*r.GIB,128*r.GIB)])));word(2)
    if chosen:
        begin('chosen');prop('bootargs',b'fixture-only\0');word(2)
    begin('reserved-memory');prop('#address-cells',struct.pack('>I',2));prop('#size-cells',struct.pack('>I',2));prop('ranges',b'')
    for i,(start,size) in enumerate(static):
        begin('fixture-'+str(i));prop('reg',struct.pack('>QQ',start,size));word(2)
    if dynamic:
        begin('fixture-dynamic');prop('size',struct.pack('>Q',32*r.MIB));word(2)
    word(2);word(2);word(9)
    reservations=b''.join(struct.pack('>QQ',start,size) for start,size in memreserve)+bytes(16)
    offstruct=40+len(reservations);offstrings=offstruct+len(tokens);total=offstrings+len(strings)
    return struct.pack('>10I',0xd00dfeed,total,offstruct,offstrings,40,17,16,0,len(strings),len(tokens))+reservations+tokens+strings


def image(size=32768000,offset=0,flags=10,file_bytes=64):
    blob=bytearray(file_bytes);blob[56:60]=b'ARM\x64'
    struct.pack_into('<QQQ',blob,8,offset,size,flags)
    return bytes(blob)


def allocations(image_base=BASE,initrd_base=BASE+64*r.MIB,dtb_base=BASE+128*r.MIB):
    return [r.Allocation(role,r.PROVIDERS[role],str(i)*32,ATTEMPT,base,size)
        for i,(role,base,size) in enumerate((('image',image_base,32*r.MIB),
            ('initrd',initrd_base,2*r.MIB),('dtb',dtb_base,2*r.MIB)),1)]


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except ValueError: pass
    else: raise AssertionError('invalid/unowned returned-layout data accepted')


def checked(k=None,initrd=b'fixture-initrd',tree=None,blocks=None,**kwargs):
    value=r.plan(image() if k is None else k,initrd,dtb() if tree is None else tree,
                 allocations() if blocks is None else blocks,attempt=ATTEMPT,**kwargs)
    for field in ('execution_enabled','allocator_call_authorized','allocator_called',
                  'runtime_allocator_results_verified','default_cma_runtime_identity_verified',
                  'default_pool_available_capacity_proven','allocation_lifetime_verified',
                  'dedicated_pool_borrowing_allowed','ownership_acquired','all_pfns_validated',
                  'current_boot_layout_validated','dt_mapping_attributes_verified','all_reservations_located',
                  'dma_safety_proven','source_and_scratch_pages_checked','loader_integrated',
                  'new_physical_base_selected','cleanup_permitted','bootargs_reviewed',
                  'handoff_architecture_verified','boot_ready'):
        assert value[field] is False
    return value


report=checked()
assert report['total_request_bytes']==36*r.MIB and not report['combined_contiguous_window_required']
assert report['image_effective_bytes']==32768000
assert report['slots'][0]['stage_bytes']==32768000 and report['slots'][0]['allocation_bytes']==32*r.MIB
assert report['slots'][0]['zero_tail_bytes']==32768000-64
assert report['dynamic_reservation_locations_unresolved']==['/reserved-memory/fixture-dynamic']
assert not report['chosen_initrd_matches']
assert report['handoff_data_only']==dict(entry=hex(BASE),x0_dtb=hex(BASE+128*r.MIB),x1=0,x2=0,x3=0)
source_tree=dtb();before=read(source_tree)
prepared,after=r.prepare_dtb(image(),b'fixture-initrd',source_tree,allocations(),attempt=ATTEMPT)
assert after['chosen_initrd_matches'] and after['only_chosen_initrd_properties_changed_semantically']
assert before==read(source_tree)
assert read(prepared)[1:]==before[1:]
assert read(prepared)[0]['/chosen']['bootargs']==b'fixture-only\0'
assert read(prepared)[0]['/chosen']['linux,initrd-end']==struct.pack('>Q',BASE+64*r.MIB+len(b'fixture-initrd'))
again,result=r.prepare_dtb(image(),b'fixture-initrd',prepared,allocations(),attempt=ATTEMPT)
assert read(again)==read(prepared) and result['chosen_initrd_matches']

# Header effective memory, text_offset, page tails, exact request/slot boundaries.
shifted=checked(k=image(offset=0x80000))
assert shifted['handoff_data_only']['entry']==hex(BASE+0x80000)
assert shifted['slots'][0]['allocation_bytes']==32*r.MIB
assert checked(k=image(flags=8))['slots'][0]['stage_bytes']==32768000
assert checked(k=image(size=32*r.MIB))['slots'][0]['stage_end_exclusive']==hex(BASE+32*r.MIB)
rounded=checked(k=image(size=32768001))
assert rounded['slots'][0]['stage_bytes']==32768000+r.PAGE
adjacent=checked(blocks=allocations(initrd_base=BASE+32*r.MIB,dtb_base=BASE+34*r.MIB))
assert adjacent['total_request_bytes']==36*r.MIB
before_image=checked(blocks=allocations(initrd_base=BASE-2*r.MIB))
assert before_image['arm64_initrd_window']['bytes']==2*r.GIB
assert checked(blocks=allocations(dtb_base=BASE+40*r.GIB))['handoff_data_only']['x0_dtb']==hex(BASE+40*r.GIB)
assert checked(initrd=b'x'*(2*r.MIB),blocks=allocations(initrd_base=BASE+32*r.GIB-2*r.MIB))['arm64_initrd_window']['bytes']==32*r.GIB
denied(checked,blocks=allocations(initrd_base=BASE+32*r.GIB))
assert r._end(r.PHYS_LIMIT-r.PAGE,r.PAGE)==r.PHYS_LIMIT
for start,size in ((r.PHYS_LIMIT-r.PAGE,2*r.PAGE),((1<<64)-1,1),(True,r.PAGE),(BASE,True),(BASE,0)):
    denied(r._end,start,size)
for attempt in ('',None,True,'A'*32):
    denied(r.plan,image(),b'fixture',dtb(),allocations(),attempt=attempt)

for role_index,field,value in ((0,'physical_start',BASE+8),(1,'physical_start',True),
        (2,'physical_start',r.PHYS_LIMIT),(0,'allocated_bytes',31*r.MIB),(2,'allocated_bytes',4*r.MIB),
        (1,'allocation_id','1'*32),(1,'attempt','b'*32),(2,'provider','dedicated-pool'),
        (0,'provenance','runtime-owned'),(0,'allocation_id',ATTEMPT),(0,'role','unknown')):
    blocks=allocations();blocks[role_index]=replace(blocks[role_index],**{field:value})
    denied(checked,blocks=blocks)
denied(checked,blocks=allocations(initrd_base=BASE+2*r.MIB))
denied(checked,blocks=allocations(dtb_base=BASE+64*r.MIB))
denied(checked,blocks=allocations()[:2])
denied(checked,blocks=[allocations()[0],allocations()[0],allocations()[2]])
for k in (b'',image()[:63],image(size=0),image(size=63),image(size=32*r.MIB,offset=0x80000),
          image(offset=1),image(flags=2),image(flags=11),image(flags=12),image(flags=0x1a),image(size=(1<<64)-1)):
    denied(checked,k=k)
denied(checked,initrd=b'');denied(checked,initrd=b'x'*(2*r.MIB+1))
denied(checked,tree=source_tree[:-1]);denied(checked,tree=source_tree+b'\0')
denied(checked,tree=dtb(chosen=False))
denied(checked,tree=dtb(memory=[(BASE,32*r.MIB)]))
denied(checked,tree=dtb(memory=[(BASE,0)]))
assert checked(tree=dtb(memory=[(BASE,0),(BASE-4*r.GIB,128*r.GIB)]))['zero_length_memory_entries_ignored']==1
denied(checked,tree=dtb(memory=[(BASE,128*r.GIB),(BASE,128*r.GIB)]))
denied(checked,tree=rewrite(dtb(),{('/','#address-cells'):struct.pack('>I',1)}))
assert checked(tree=rewrite(dtb(),{('/reserved-memory/fixture-dynamic','alloc-ranges'):
    struct.pack('>QQ',0x100000000,0xfffffffeffffffff)}))['dynamic_reservation_locations_unresolved']
denied(checked,tree=rewrite(dtb(),{('/reserved-memory/fixture-dynamic','alloc-ranges'):
    struct.pack('>QQ',(1<<64)-1,2)}))
denied(checked,tree=dtb(static=[(BASE+128*r.MIB+r.MIB,r.PAGE)]))  # DT slot padding is not borrowable
denied(checked,tree=dtb(memreserve=[(BASE+r.MIB,r.PAGE)]))
denied(checked,extra_exclusions=[r.Exclusion('descriptor-page',BASE+64*r.MIB+r.MIB,r.PAGE)])
denied(checked,extra_exclusions=[r.Exclusion('source-page',r.PHYS_LIMIT-r.PAGE,2*r.PAGE)])
denied(checked,extra_exclusions=[r.Exclusion('shell;command',0,r.PAGE)])
assert checked(extra_exclusions=[r.Exclusion('source-page',BASE+256*r.MIB,r.PAGE)])['static_exclusions_checked']==1

# DT rewrite growth must be validated AGAIN, not staged into an undersized slot.
small=dtb(padding=b'');padded=dtb(padding=b'x'*((2*r.MIB-len(small))//4*4))
assert len(padded)<=2*r.MIB
denied(r.prepare_dtb,image(),b'fixture',padded,allocations(),attempt=ATTEMPT)

# Real payload measurements, but ALWAYS fictitious RAM/DT and allocation records.
root=Path(__file__).resolve().parents[2]
real_image=(root/'.work/usb-trim3-build-out/arch/arm64/boot/Image').read_bytes()
real_initrd=(root/'quest3/usb-minimal/quest3-usb2-minimal.cpio.gz').read_bytes()
real_dtb=(root/'private-diagnostics/memory-maps-20261117T101933Z/live.dtb').read_bytes()
candidate_dtb=(root/'quest3/usb-minimal/quest3-usb2-peripheral.private.dtb').read_bytes()
assessment=json.loads((root/'quest3/usb-trim/trim3-allocation-assessment.json').read_text())
for name,blob in (('image',real_image),('initrd',real_initrd),('dtb',real_dtb)):
    assert hashlib.sha256(blob).hexdigest()==assessment['input_sha256'][name]
actual=checked(k=real_image,initrd=real_initrd)
assert actual['total_request_bytes']==36*r.MIB and actual['slots'][0]['zero_tail_bytes']==1615360
assert len(real_dtb)<2*r.MIB and r._dt(real_dtb)[0]['/chosen']
assert len(candidate_dtb)<2*r.MIB and r._dt(candidate_dtb)[0]['/chosen']
assert len(real_image)==31152640 and actual['image_effective_bytes']==32768000
denied(checked,k=real_image,initrd=real_initrd,tree=real_dtb)  # Fictitious 64GiB base is not real Quest RAM.

source=Path(r.__file__).read_text()
for forbidden in ('import os','import subprocess','import socket','open(', 'exec(', 'eval(', '0x90000000','0x93000000','0x93200000'):
    assert forbidden not in source
print('PASS returned-allocation host layout: typed separate slots, ARM64 header/page/window bounds, static DT exclusions, chosen-only rewrite, trim3 measurements and no provider/ownership/loader action')
