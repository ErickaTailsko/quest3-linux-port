#!/usr/bin/env python3
"""Native HOST/UBSan arithmetic tests and differential checks, never a loader."""
import ctypes as c
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import tempfile

here=Path(__file__).resolve().parent
# Reuse and recheck the established Python fixtures, including real trim3 sizes.
spec=importlib.util.spec_from_file_location('returned_layout_cases',here/'test-returned-layout.py')
cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)
r=cases.r

HARNESS=r'''
#include <stddef.h>
#define Q3RL_HOST_TEST
#include "returned-layout-core.h"
_Static_assert(sizeof(q3rl_u64) == 8, "u64 width");
int fixture_validate(const struct q3rl_request *r, struct q3rl_geometry *o)
{ return q3rl_validate_geometry(r, o); }
int fixture_overlap(const struct q3rl_request *r, q3rl_u64 a, q3rl_u64 n, unsigned int *o)
{ return q3rl_destination_overlap_mask(r, a, n, o); }
int fixture_end(q3rl_u64 a, q3rl_u64 n, q3rl_u64 *o)
{ return q3rl_range_end(a, n, o); }
int fixture_round(q3rl_u64 a, q3rl_u64 n, q3rl_u64 *o)
{ return q3rl_round_up(a, n, o); }
size_t fixture_request_size(void) { return sizeof(struct q3rl_request); }
size_t fixture_geometry_size(void) { return sizeof(struct q3rl_geometry); }
'''
FLAGS=['-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',
       '-fsanitize=undefined','-fno-sanitize-recover=undefined',
       '-fstack-protector-strong','-D_FORTIFY_SOURCE=2','-Wl,-z,relro,-z,now,-z,noexecstack']


class Slot(c.Structure):
    _fields_=[('role',c.c_uint),('provider',c.c_uint),('start',c.c_uint64),('bytes',c.c_uint64)]


class Request(c.Structure):
    _fields_=[(name,c.c_uint64) for name in ('image_file_bytes','image_offset','image_size',
        'image_flags','initrd_file_bytes','dtb_file_bytes')]+[('slot_count',c.c_uint),('slots',Slot*3)]


class Segment(c.Structure):
    _fields_=[(name,c.c_uint64) for name in ('allocation_start','allocation_end','allocation_bytes',
        'payload_start','file_bytes','file_end','stage_bytes','stage_end','zero_tail_bytes','copy_pages')]


class Geometry(c.Structure):
    _fields_=[('slots',Segment*3)]+[(name,c.c_uint64) for name in ('image_entry','dtb_address',
        'initrd_start','initrd_end','window_start','window_end','window_bytes','total_request_bytes')]+[
        (name,c.c_uint) for name in ('geometry_only','ownership_acquired','boot_ready')]


def request(image=None,initrd=b'fixture-initrd',tree=None,blocks=None):
    image=cases.image() if image is None else image
    tree=cases.dtb() if tree is None else tree
    blocks=cases.allocations() if blocks is None else blocks
    offset,size,flags=struct.unpack_from('<QQQ',image,8)
    slots=(Slot*3)(*(Slot(('image','initrd','dtb').index(a.role),
        1 if a.provider=='default-cma-image' else 2 if a.provider in ('buddy-initrd','buddy-dtb') else 127,
        a.physical_start,a.allocated_bytes) for a in blocks))
    return Request(len(image),offset,size,flags,len(initrd),len(tree),3,slots)


def clone(value): return type(value).from_buffer_copy(bytes(value))


def fresh_output():
    out=Geometry();c.memset(c.byref(out),0xa5,c.sizeof(out))
    return out


with tempfile.TemporaryDirectory(prefix='q3-layout-core-',dir='/tmp/opencode') as temporary:
    tmp=Path(temporary);source=tmp/'harness.c';library=tmp/'layout-host.so'
    source.write_text(HARNESS)
    subprocess.run([os.environ.get('CC','cc'),*FLAGS,'-I',str(here),str(source),'-o',str(library)],check=True,timeout=60)
    lib=c.CDLL(str(library))
    lib.fixture_validate.argtypes=[c.POINTER(Request),c.POINTER(Geometry)];lib.fixture_validate.restype=c.c_int
    lib.fixture_overlap.argtypes=[c.POINTER(Request),c.c_uint64,c.c_uint64,c.POINTER(c.c_uint)];lib.fixture_overlap.restype=c.c_int
    for name in ('fixture_end','fixture_round'):
        func=getattr(lib,name);func.argtypes=[c.c_uint64,c.c_uint64,c.POINTER(c.c_uint64)];func.restype=c.c_int
    lib.fixture_request_size.restype=c.c_size_t;lib.fixture_geometry_size.restype=c.c_size_t
    assert lib.fixture_request_size()==c.sizeof(Request) and lib.fixture_geometry_size()==c.sizeof(Geometry)
    validated=0;rejected=0;overlap_queries=0

    def compare(k=None,rd=b'fixture-initrd',tree=None,blocks=None):
        global validated,rejected
        k=cases.image() if k is None else k;tree=cases.dtb() if tree is None else tree
        blocks=cases.allocations() if blocks is None else blocks
        req=request(k,rd,tree,blocks);out=fresh_output();untouched=bytes(out)
        status=lib.fixture_validate(c.byref(req),c.byref(out))
        try: expected=r.plan(k,rd,tree,blocks,attempt=cases.ATTEMPT)
        except ValueError:
            assert status<0 and bytes(out)==untouched
            rejected+=1;return req,None
        assert status==0 and out.geometry_only==1 and out.ownership_acquired==out.boot_ready==0
        for actual,slot in zip(out.slots,expected['slots']):
            for cname,pname in (('allocation_start','allocation_start'),('allocation_end','allocation_end_exclusive'),
                    ('allocation_bytes','allocation_bytes'),('payload_start','payload_start'),('file_bytes','file_bytes'),
                    ('file_end','file_end_exclusive'),('stage_bytes','stage_bytes'),('stage_end','stage_end_exclusive'),
                    ('zero_tail_bytes','zero_tail_bytes'),('copy_pages','copy_pages')):
                value=slot[pname];assert getattr(actual,cname)==(int(value,16) if isinstance(value,str) else value)
        assert out.image_entry==int(expected['handoff_data_only']['entry'],16)
        assert out.dtb_address==int(expected['handoff_data_only']['x0_dtb'],16)
        assert out.initrd_start==int(expected['chosen_initrd_expected']['linux,initrd-start'],16)
        assert out.initrd_end==int(expected['chosen_initrd_expected']['linux,initrd-end'],16)
        assert out.window_start==int(expected['arm64_initrd_window']['start'],16)
        assert out.window_end==int(expected['arm64_initrd_window']['end_exclusive'],16)
        assert out.window_bytes==expected['arm64_initrd_window']['bytes']
        assert out.total_request_bytes==expected['total_request_bytes']
        validated+=1;return req,out

    def overlap(req,start,size,expected=None):
        global overlap_queries
        mask=c.c_uint(0xa5a5a5a5);status=lib.fixture_overlap(c.byref(req),start,size,c.byref(mask))
        if expected is None: assert status<0 and mask.value==0xa5a5a5a5
        else: assert status==0 and mask.value==expected
        overlap_queries+=1

    req,geometry=compare()
    compare(cases.real_image,cases.real_initrd)
    shifted,_=compare(cases.image(offset=0x80000))
    compare(blocks=cases.allocations(dtb_base=cases.BASE+40*r.GIB))
    compare(rd=b'x'*(2*r.MIB),blocks=cases.allocations(initrd_base=cases.BASE+32*r.GIB-2*r.MIB))
    compare(blocks=cases.allocations(initrd_base=cases.BASE+32*r.GIB))
    compare(cases.image(size=32*r.MIB,offset=0x80000))
    for i,slot in enumerate(geometry.slots):
        bit=1<<i
        overlap(req,slot.allocation_start,r.PAGE,bit)
        overlap(req,slot.allocation_end-r.PAGE,r.PAGE,bit)
        overlap(req,slot.allocation_start-1,1,0)
        overlap(req,slot.allocation_start-1,2,bit)
        overlap(req,slot.allocation_end-1,1,bit)
        overlap(req,slot.allocation_end,r.PAGE,0)
    overlap(req,geometry.slots[0].stage_end,r.PAGE,1)  # Image trailing padding is still owned destination scope.
    overlap(shifted,cases.BASE,r.PAGE,1)  # text_offset prefix must also be excluded.
    overlap(req,cases.BASE,geometry.slots[2].allocation_end-cases.BASE,7)
    overlap(req,geometry.slots[0].allocation_end,r.PAGE,0)  # Gap is NOT proof of usable RAM.
    overlap(req,0,r.PAGE,0)
    for kind in ('source-page','descriptor-page','relocation-code','page-table','scratch'):
        overlap(req,geometry.slots[0].stage_end,r.PAGE,1)
        assert geometry.ownership_acquired==geometry.boot_ready==0
    upper_blocks=cases.allocations(image_base=r.PHYS_LIMIT-64*r.MIB,
        initrd_base=r.PHYS_LIMIT-16*r.MIB,dtb_base=r.PHYS_LIMIT-2*r.MIB)
    upper,upper_geometry=compare(tree=cases.dtb(memory=[(r.PHYS_LIMIT-r.GIB,r.GIB)]),blocks=upper_blocks)
    assert upper_geometry.window_end==r.PHYS_LIMIT
    overlap(upper,r.PHYS_LIMIT-r.PAGE,r.PAGE,4)
    overlap(upper,r.PHYS_LIMIT-r.PAGE,r.PAGE+1)
    for start,size in ((cases.BASE,0),(r.PHYS_LIMIT,1),(r.PHYS_LIMIT-r.PAGE,2*r.PAGE),((1<<64)-1,1)):
        overlap(req,start,size)

    # Every validation error leaves caller's output untouched; invalid layouts
    # must never turn into a zero mask that looks like a negative overlap check.
    for field,value in (('slot_count',0),('slot_count',4),('image_size',0),('image_size',(1<<64)-1),
            ('image_file_bytes',(1<<64)-1),('image_offset',(1<<64)-1),('image_flags',0x1a),
            ('initrd_file_bytes',0),('dtb_file_bytes',39)):
        bad=clone(req);setattr(bad,field,value);out=fresh_output();before=bytes(out)
        assert lib.fixture_validate(c.byref(bad),c.byref(out))<0 and bytes(out)==before
        overlap(bad,cases.BASE,r.PAGE)
    for field,value in (('role',0xffffffff),('role',0),('provider',99),('start',r.PHYS_LIMIT),
                        ('start',cases.BASE+8),('bytes',(1<<64)-1)):
        bad=clone(req);setattr(bad.slots[1],field,value);out=fresh_output();before=bytes(out)
        assert lib.fixture_validate(c.byref(bad),c.byref(out))<0 and bytes(out)==before
        overlap(bad,cases.BASE,r.PAGE)
    out=fresh_output();before=bytes(out)
    assert lib.fixture_validate(None,c.byref(out))<0 and bytes(out)==before
    assert lib.fixture_validate(c.byref(req),None)<0
    assert lib.fixture_overlap(c.byref(req),cases.BASE,r.PAGE,None)<0
    end=c.c_uint64(123)
    assert lib.fixture_end(r.PHYS_LIMIT-r.PAGE,r.PAGE,c.byref(end))==0 and end.value==r.PHYS_LIMIT
    for start,size in ((r.PHYS_LIMIT-r.PAGE,2*r.PAGE),((1<<64)-1,1),(0,0)):
        end.value=123;assert lib.fixture_end(start,size,c.byref(end))<0 and end.value==123
    for value,align in (((1<<64)-1,4096),(1,0),(1,3)):
        end.value=123;assert lib.fixture_round(value,align,c.byref(end))<0 and end.value==123

    # This core deliberately accepts numerical DT size alone, not its format,
    # RAM/reservations, allocation identity/attempt or lifetime. Full guards are
    # higher-level obligations; numerical success is never boot admission.
    numeric_only=clone(req);numeric_only.dtb_file_bytes=40;out=fresh_output()
    assert lib.fixture_validate(c.byref(numeric_only),c.byref(out))==0
    assert out.geometry_only==1 and out.ownership_acquired==out.boot_ready==0
    invalid_ram=cases.dtb(memory=[(cases.BASE,32*r.MIB)])
    try: r.plan(cases.image(),b'fixture-initrd',invalid_ram,cases.allocations(),attempt=cases.ATTEMPT)
    except ValueError: pass
    else: raise AssertionError('Python DT coverage guard missing')
    numeric_only=request(tree=invalid_ram)
    assert lib.fixture_validate(c.byref(numeric_only),c.byref(out))==0 and out.geometry_only==1
    wrong_context=cases.allocations();wrong_context[0]=replace(wrong_context[0],attempt='b'*32)
    try: r.plan(cases.image(),b'fixture-initrd',cases.dtb(),wrong_context,attempt=cases.ATTEMPT)
    except ValueError: pass
    else: raise AssertionError('Python allocation-context guard missing')
    numeric_only=request(blocks=wrong_context)
    assert lib.fixture_validate(c.byref(numeric_only),c.byref(out))==0 and out.ownership_acquired==out.boot_ready==0

    seed=20261118;rng=random.Random(seed)
    for index in range(2000):
        size=rng.randint(64,32*r.MIB);offset=rng.choice((0,0x80000));flags=rng.choice((8,10,10,10))
        k=cases.image(size=size,offset=offset,flags=flags,file_bytes=rng.randint(64,min(size,1024)))
        rd=b'x'*rng.randint(1,8192)
        blocks=cases.allocations(image_base=cases.BASE+rng.randrange(32)*r.ALIGN,
            initrd_base=cases.BASE+rng.randrange(-2,33*512)*r.ALIGN,
            dtb_base=cases.BASE+rng.randrange(64,64*512)*r.ALIGN)
        image_request=r._up(offset+r._up(size,r.PAGE),r.ALIGN)
        blocks[0]=replace(blocks[0],allocated_bytes=image_request)
        rng.shuffle(blocks)
        trial,actual=compare(k,rd,blocks=blocks)
        if actual is None: continue
        start=cases.BASE+rng.randrange(-2,65*512)*r.ALIGN+rng.randrange(-4096,4096)
        length=rng.randint(1,64*r.MIB)
        expected=sum(1<<i for i,slot in enumerate(actual.slots)
                     if start<slot.allocation_end and slot.allocation_start<start+length)
        overlap(trial,start,length,expected)
    SUMMARY=dict(seed=seed,random_cases=2000,accepted_comparisons=validated,
                 rejected_comparisons=rejected,overlap_queries=overlap_queries,
                 ubsan_enabled=True,loader_integrated=False,allocator_called=False,boot_ready=False)

source=(here/'returned-layout-core.h').read_text()
for forbidden in ('cma_alloc(', 'alloc_page(', 'free_page(', 'memcpy(', 'qkx_enter(', '0x90000000', '0x93000000', '0x93200000'):
    assert forbidden not in source
assert 'returned-layout-core.h' not in (here.parent/'module/loader.c').read_text()
print('PASS host C returned-layout core: Python differential, checked u64/page/window arithmetic, full-slot source/scratch intersection masks, untouched error outputs and UBSan; no allocator/loader action')
print(json.dumps(SUMMARY,sort_keys=True))
