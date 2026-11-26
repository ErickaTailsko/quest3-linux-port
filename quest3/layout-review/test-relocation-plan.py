#!/usr/bin/env python3
"""Source snapshots/descriptors in HOST fixtures only; no physical copying."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import random
import struct

import relocation_plan as s
import returned_layout as r

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('layout_cases',here/'test-returned-layout.py')
cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except ValueError: pass
    else: raise AssertionError('invalid fixture staging/descriptor/lifetime metadata accepted')


def safe(result):
    for field,value in s.flags().items(): assert result[field] is value is False
    return result


def fixture(*,k=None,rd=b'fixture-initrd',tree=None,scratch=0):
    k=cases.image(size=3*r.PAGE,file_bytes=r.PAGE+17) if k is None else k
    raw_tree=cases.dtb() if tree is None else tree
    offset,size,_=struct.unpack_from('<QQQ',k,8)
    blocks=cases.allocations();blocks[0]=replace(blocks[0],allocated_bytes=r._up(offset+r._up(size,r.PAGE),r.ALIGN))
    prepared,layout=r.prepare_dtb(k,rd,raw_tree,blocks,attempt=cases.ATTEMPT)
    payloads={'image':k,'initrd':rd,'dtb':prepared};pages=[];serial=1000
    def page(kind,address,index=0,role='',contents=b''):
        nonlocal serial
        result=s.Page(kind,f'{serial:032x}',cases.ATTEMPT,address,index,role,contents);serial+=1
        return result
    for slot in layout['slots']:
        for index in range(slot['copy_pages']):
            pages.append(page('source',cases.BASE+2*r.GIB+len(pages)*2*r.PAGE,index,slot['role'],
                              s.expected_source_page(payloads[slot['role']],index)))
    sources=len(pages);descriptors=(sources+s.DESCRIPTOR_CAPACITY-1)//s.DESCRIPTOR_CAPACITY
    for index in range(descriptors): pages.append(page('descriptor',cases.BASE+4*r.GIB+index*r.PAGE,index))
    for index,kind in enumerate(('relocation-code','pgd','pud')):
        pages.append(page(kind,cases.BASE+6*r.GIB+index*r.PAGE))
    for index in range(scratch): pages.append(page('scratch',cases.BASE+7*r.GIB+index*r.PAGE,index))
    return k,rd,prepared,blocks,pages


def build(data): return s.build(*data,attempt=cases.ATTEMPT)


data=fixture(scratch=2);plan=build(data);summary=safe(s.summary(plan))
assert summary['source_pages']==5 and summary['descriptor_pages']==1 and summary['auxiliary_pages']==5
assert summary['total_work_pages']==11 and s.DESCRIPTOR_CAPACITY==255
assert summary['copy_pages_by_role']=={'image':3,'initrd':1,'dtb':1}
assert summary['dynamic_reservations_unresolved']==['/reserved-memory/fixture-dynamic']
assert plan.copies[1].file_bytes==17 and plan.copies[1].zero_bytes==r.PAGE-17
assert plan.copies[2].file_bytes==0 and plan.copies[2].zero_bytes==r.PAGE
assert [copy.destination for copy in plan.copies[:3]]==[cases.BASE+i*r.PAGE for i in range(3)]
assert plan.copies[1].source-plan.copies[0].source==2*r.PAGE  # Scatter source pages are not final Image scatter.
assert safe(s.validate_descriptor_chain(plan,plan.descriptors))['copy_pages']==5
assert safe(s.review_retained_records(plan,data[3],data[4]))['supplied_retained_records_match']
shuffled=list(data[4]);random.Random(18).shuffle(shuffled)
assert s.build(*data[:3],list(reversed(data[3])),shuffled,attempt=cases.ATTEMPT)==plan
assert safe(s.review_retained_records(plan,list(reversed(data[3])),shuffled))['supplied_retained_records_match']

for total in (3,254,255,256,510,511):
    boundary_data=fixture(k=cases.image(size=(total-2)*r.PAGE))
    boundary=build(boundary_data)
    assert len(boundary.copies)==total
    assert len(boundary.descriptors)==(total+254)//255
    counts=[struct.unpack_from('<QQ',d.contents)[1] for d in boundary.descriptors]
    assert counts==[min(255,total-i*255) for i in range(len(counts))]
    assert struct.unpack_from('<Q',boundary.descriptors[-1].contents)[0]==0
    assert safe(s.validate_descriptor_chain(boundary,tuple(reversed(boundary.descriptors))))['copy_pages']==total

# Every class of work page is excluded from the COMPLETE destination slots.
for kind in s.KINDS:
    pages=list(data[4]);index=next(i for i,p in enumerate(pages) if p.kind==kind)
    pages[index]=replace(pages[index],physical_start=cases.BASE+r.MIB)  # Image allocation padding, not copied bytes.
    denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)
shifted=fixture(k=cases.image(size=3*r.PAGE,offset=0x80000))
pages=list(shifted[4]);pages[0]=replace(pages[0],physical_start=cases.BASE)
denied(s.build,*shifted[:4],pages,attempt=cases.ATTEMPT)
for field,value in (('kind','unknown'),('index',False),('index',-1),('role','unknown'),
                    ('physical_start',r.PHYS_LIMIT),('physical_start',cases.BASE+1),
                    ('physical_start',cases.BASE+200*r.GIB),('attempt','b'*32),
                    ('allocation_id','1'*32),('provenance','runtime-owned'),
                    ('contents',bytes(r.PAGE-1)),('contents',bytearray(r.PAGE))):
    pages=list(data[4]);pages[0]=replace(pages[0],**{field:value})
    denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)
pages=list(data[4]);pages[0]=replace(pages[0],physical_start=next(p.physical_start for p in pages if p.kind=='descriptor'))
denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)
pages=list(data[4]);pages.append(replace(pages[0],allocation_id='f'*32,physical_start=cases.BASE+3*r.GIB))
denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)  # Duplicate role/index, even with distinct token/address.
for kind in ('source','descriptor','relocation-code','pgd','pud'):
    pages=list(data[4]);pages.pop(next(i for i,p in enumerate(pages) if p.kind==kind))
    denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)
for kind in ('relocation-code','pgd','pud'):
    pages=list(data[4]);original=next(p for p in pages if p.kind==kind)
    pages.append(replace(original,allocation_id='e'*32,physical_start=cases.BASE+8*r.GIB))
    denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)
pages=list(data[4]);index=next(i for i,p in enumerate(pages) if p.kind=='scratch')
pages[index]=replace(pages[index],index=7)
denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)
pages=list(data[4]);index=next(i for i,p in enumerate(pages) if p.kind=='pgd')
pages[index]=replace(pages[index],contents=b'not a built page table')
denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)
denied(build,fixture(scratch=s.MAX_SCRATCH+1))
denied(s.build,*data[:4],[data[4][0]]*(s.MAX_WORK_PAGES+1),attempt=cases.ATTEMPT)

# File tail and BSS are required zero, not unspecified data from a target page.
for image_index in (1,2):
    pages=list(data[4]);index=next(i for i,p in enumerate(pages) if p.role=='image' and p.index==image_index)
    raw=bytearray(pages[index].contents);raw[-1]=1
    pages[index]=replace(pages[index],contents=bytes(raw))
    denied(s.build,*data[:4],pages,attempt=cases.ATTEMPT)
denied(s.build,data[0],data[1],cases.dtb(),data[3],data[4],attempt=cases.ATTEMPT)  # chosen not prepared
denied(build,fixture(tree=cases.dtb(static=[(cases.BASE+2*r.GIB,r.PAGE)])))
denied(build,fixture(tree=cases.dtb(memory=[(cases.BASE,256*r.MIB)])))

# Corrupted descriptors are parsed as host bytes, never physical pointer reads.
multi=build(fixture(k=cases.image(size=254*r.PAGE)))
assert len(multi.descriptors)==2
for field_offset,value in ((0,multi.descriptors[0].physical_start),(0,0),(0,r.PHYS_LIMIT),
                           (8,0),(8,256),(8,(1<<64)-1),(16,multi.copies[0].source+r.PAGE),
                           (24,multi.copies[0].destination+r.PAGE)):
    changed=list(multi.descriptors);raw=bytearray(changed[0].contents);struct.pack_into('<Q',raw,field_offset,value)
    changed[0]=replace(changed[0],contents=bytes(raw))
    denied(s.validate_descriptor_chain,multi,changed)
changed=list(multi.descriptors);raw=bytearray(changed[-1].contents);raw[-1]=1
changed[-1]=replace(changed[-1],contents=bytes(raw));denied(s.validate_descriptor_chain,multi,changed)
denied(s.validate_descriptor_chain,multi,multi.descriptors[:1])
denied(s.validate_descriptor_chain,multi,[multi.descriptors[0],multi.descriptors[0]])
changed=list(multi.descriptors);changed[-1]=replace(changed[-1],allocation_id='e'*32)
denied(s.validate_descriptor_chain,multi,changed)
changed=list(multi.descriptors);changed[-1]=replace(changed[-1],contents=changed[-1].contents[:-1])
denied(s.validate_descriptor_chain,multi,changed)

# Metadata retention is not physical lifetime. Replaying identical fixture
# snapshots still matches; no actual live-handle verification is inferred.
clones=[replace(p) for p in data[4]]
assert not safe(s.review_retained_records(plan,data[3],clones))['actual_handles_live_verified']
denied(s.review_retained_records,plan,data[3],data[4][:-1])
changed=list(data[4]);changed[0]=replace(changed[0],allocation_id='e'*32)
denied(s.review_retained_records,plan,data[3],changed)
changed=list(data[3]);changed[0]=replace(changed[0],physical_start=cases.BASE+32*r.MIB)
denied(s.review_retained_records,plan,changed,data[4])

# Real trim3/initrd, but synthetic DT/RAM/physical resources. No device boot DT.
large_data=fixture(k=cases.real_image,rd=cases.real_initrd,tree=cases.dtb(padding=b'x'*698000))
large=build(large_data);large_summary=safe(s.summary(large))
assert large_summary['source_pages']==8317 and large_summary['descriptor_pages']==33
assert large_summary['auxiliary_pages']==3 and large_summary['total_work_pages']==8353
assert large_summary['copy_pages_by_role']=={'image':8000,'initrd':146,'dtb':171}
assert large_summary['destination_requested_bytes']==36*r.MIB
assert large_summary['work_page_bytes']==8353*r.PAGE
assert large_summary['modeled_retained_bytes']==71962624  # 68.62890625 MiB, not only the 36 MiB destinations.
assert not large_summary['page_cache_and_rejected_pages_included']
assert safe(s.validate_descriptor_chain(large,large.descriptors))['copy_pages']==8317
assert safe(s.review_retained_records(large,large_data[3],large_data[4]))['supplied_retained_records_match']

source=Path(s.__file__).read_text()
for forbidden in ('import os','import socket','import subprocess','open(', 'exec(', 'eval(', 'import controller', 'def release'):
    assert forbidden not in source
print('PASS host relocation plan: immutable source snapshots/zero-fill, typed retained records, all-work aliases/destination exclusion, 255-entry linked descriptors and corruption checks; no physical read/write/ownership/handoff')
