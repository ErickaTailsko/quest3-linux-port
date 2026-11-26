#!/usr/bin/env python3
"""Synthetic ELF data only; do not assemble, link, load or execute fixture bytes."""
import json
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

import cache_leaf_static_review as v
from relocation_plan import flags

BTI=0xd503245f
PAC=0xd503233f
AUT=0xd50323bf
RET=0xd65f03c0
NAME='fixture_leaf'


def fixture(words=(BTI,PAC,AUT,RET),*,escape=False,debug=False,alias=False,reloc_type=283,addend=0,body_reloc=False,section_ref=False):
    """Minimal unlinked, non-module ELF fixture; no .modinfo or executable entry."""
    text=struct.pack('<'+'I'*len(words),*words)+struct.pack('<II',0x94000000,RET)
    strings=b'\0'+NAME.encode()+b'\0fixture_caller\0alias_leaf\0'
    symbols=bytes(24)+struct.pack('<IBBHQQ',1,0x12,0,1,0,len(words)*4)
    symbols+=struct.pack('<IBBHQQ',len(NAME)+2,0x12,0,1,len(words)*4,8)
    if alias: symbols+=struct.pack('<IBBHQQ',strings.index(b'alias_leaf'),0x12,0,1,0,len(words)*4)
    if section_ref: symbols+=struct.pack('<IBBHQQ',0,3,0,1,0,0)
    # name,type,flags,data,link,info,alignment,entsize
    specs=[('',0,0,b'',0,0,0,0),('.text',1,6,text,0,0,4,0),
           ('.strtab',3,0,strings,0,0,1,0),('.symtab',2,0,symbols,2,1,8,24),
           ('.rela.text',4,0,struct.pack('<QQq',len(words)*4,(1<<32)|reloc_type,addend),3,1,8,24)]
    if body_reloc:
        specs[4]=(*specs[4][:3],specs[4][3]+struct.pack('<QQq',4,(1<<32)|257,0),*specs[4][4:])
    if escape or debug or section_ref:
        target=len(specs)
        specs.append(('.debug_info' if debug else '.data',1,0 if debug else 3,bytes(8),0,0,8,0))
        si=len(symbols)//24-1 if section_ref else 1
        specs.append(('.rela.extra',4,0,struct.pack('<QQq',0,(si<<32)|257,0),3,target,8,24))
    names=b'\0';offsets={'':0}
    for name,*_ in specs[1:]:
        offsets[name]=len(names);names+=name.encode()+b'\0'
    offsets['.shstrtab']=len(names);names+=b'.shstrtab\0'
    specs.append(('.shstrtab',3,0,names,0,0,1,0))
    data=bytearray(64);headers=[]
    for name,typ,fl,blob,link,info,align,entsize in specs:
        if not typ: headers.append((0,)*10);continue
        data.extend(bytes((-len(data))%max(align,1)));offset=len(data);data.extend(blob)
        headers.append((offsets[name],typ,fl,0,offset,len(blob),link,info,align,entsize))
    data.extend(bytes((-len(data))%8));shoff=len(data)
    for header in headers: data.extend(struct.pack('<IIQQQQIIQQ',*header))
    ident=b'\x7fELF\x02\x01\x01'+bytes(9)
    struct.pack_into('<16sHHIQQQIHHHHHH',data,0,ident,1,183,1,0,0,shoff,0,64,0,0,64,len(headers),len(headers)-1)
    return bytes(data)


def inspect(data,**kwargs):
    report=v.inspect_bytes(data,symbol=NAME,**kwargs)
    for field in (*flags(),'helper_approved','runtime_admission_enabled','authorization_verified',
                  'cache_protocol_verified','actual_lifetime_proven','inspected_bytes_executed'):
        assert report[field] is False
    assert report['overall'] in ('PENDING','REJECT')  # Never a whole-contract approval.
    return report


def rejected(data,criterion):
    report=inspect(data)
    assert report['overall']=='REJECT' and report['checks'][criterion]['status']=='REJECT',report


DATA=fixture();report=inspect(DATA)
assert report['overall']=='PENDING'
for key in ('L06','L07','L08','L09','L13'): assert report['checks'][key]['status']=='PASS'
for key in ('L01','L02','L03','L04','L05','L10','L11','L12','L14'): assert report['checks'][key]['status']=='PENDING'
assert report['observations']['direct_calls_observed']==1
assert inspect(fixture(debug=True))['checks']['L04']['status']=='PENDING'
rejected(fixture(escape=True),'L04')
rejected(fixture(section_ref=True),'L04')
rejected(fixture(alias=True),'L09')
rejected(fixture(reloc_type=282),'L03')
rejected(fixture(addend=4),'L03')
rejected(fixture((RET,PAC,AUT,RET)),'L06')
for words in ((BTI,RET),(BTI,PAC,RET),(BTI,AUT,RET),
              (BTI,PAC,0xd50323ff,RET),(BTI,PAC,PAC,AUT,RET),
              (BTI,PAC,0xb4000041,AUT,RET)):  # CBZ x1 skips authentication.
    rejected(fixture(words),'L08')
assert inspect(fixture((BTI,0xd503237f,0xd50323ff,RET)))['checks']['L08']['status']=='PASS'
assert inspect(fixture((BTI,PAC,0xd65f0bff)))['checks']['L08']['status']=='PASS'
assert inspect(fixture((BTI,0xd503237f,0xd65f0fff)))['checks']['L08']['status']=='PASS'
rejected(fixture((BTI,PAC,0xd65f0fff)),'L08')
for word in (0xaa0003f2,0xaa0003f3,0xd10043ff,0xd280001e):  # x18/x19/SP/LR clobbers.
    rejected(fixture((BTI,PAC,word,AUT,RET)),'L07')
for word in (0x94000000,0xd63f0000,0xd5034fdf):
    rejected(fixture((BTI,PAC,word,AUT,RET)),'L13')
rejected(fixture((BTI,PAC,0xd50b7b20,0xd5033f9f,AUT,RET)),'L12')  # PoU-only.
rejected(fixture((BTI,PAC,0xd50b7e20,AUT,RET)),'L12')  # Missing DSB SY.
assert inspect(fixture((BTI,PAC,0xd50b7e20,0xd5033f9f,AUT,RET)))['checks']['L12']['status']=='PENDING'
unknown=inspect(fixture((BTI,PAC,0xffffffff,AUT,RET)))
assert unknown['checks']['L07']['status']=='PENDING' and unknown['checks']['L08']['status']=='PENDING'
assert inspect(fixture(body_reloc=True))['checks']['L09']['status']=='PENDING'
rejected(fixture((BTI,PAC,0x14000002,AUT)),'L08')  # Branch into caller, outside leaf.
loop=inspect(fixture((BTI,PAC,0x14000000)))
assert loop['checks']['L08']['status']=='PENDING' and not loop['observations']['reachable_returns']

for data in (b'',b'\x7fELF',DATA[:63],DATA[:-1],bytearray(DATA),DATA+bytes(v.MAX_BYTES)):
    rejected(data,'L09')
for offset,fmt,value in ((4,'B',1),(5,'B',2),(16,'H',2),(18,'H',62),(58,'H',0),(60,'H',513),(62,'H',0)):
    changed=bytearray(DATA);struct.pack_into('<'+fmt,changed,offset,value);rejected(bytes(changed),'L09')
shoff=struct.unpack_from('<Q',DATA,40)[0]
for offset,fmt,value in ((shoff+64+24,'Q',len(DATA)),  # text file offset.
                         (shoff+64+8,'Q',2),         # no executable flag.
                         (shoff+64+8,'Q',6|0x800),   # compressed executable bytes unsupported.
                         (shoff+64+48,'Q',1),        # insufficient declared instruction alignment.
                         (shoff+3*64+56,'Q',8),      # invalid symbol entsize.
                         (shoff+4*64+40,'I',99)):    # relocation symbol-table link.
    changed=bytearray(DATA);struct.pack_into('<'+fmt,changed,offset,value);rejected(bytes(changed),'L09')
symbol_start=struct.unpack_from('<Q',DATA,shoff+3*64+24)[0]
changed=bytearray(DATA);struct.pack_into('<H',changed,symbol_start+2*24+6,0xffff)
rejected(bytes(changed),'L09')
old_bound=v.MAX_CFG_STATES
try:
    v.MAX_CFG_STATES=1
    assert inspect(DATA)['checks']['L08']['status']=='PENDING'
finally: v.MAX_CFG_STATES=old_bound
old_name_budget=v.MAX_NAME_SCAN_BYTES
try:
    v.MAX_NAME_SCAN_BYTES=1
    rejected(DATA,'L09')
finally: v.MAX_NAME_SCAN_BYTES=old_name_budget
old_string_limit=v.MAX_STRING
try:
    v.MAX_STRING=2
    rejected(DATA,'L09')
finally: v.MAX_STRING=old_string_limit
# Indexed caller queries retain ambiguity and half-open instruction bounds.
functions=[dict(info=2,section=1,value=i*8,size=8,name=f'f{i}') for i in range(10000)]
queries={(1,i*8) for i in range(10000)}
mapped=v._caller_map(functions,queries)
assert len(mapped)==10000 and all(mapped[(1,i*8)]==f'f{i}' for i in range(10000))
functions.append(dict(info=2,section=1,value=0,size=4,name='alias'))
mapped=v._caller_map(functions,{(1,0),(1,4),(1,6),(2,0)})
assert mapped=={(1,0):None,(1,4):'f0',(1,6):None,(2,0):None}
fuzz=random.Random(191127)
for _ in range(200):
    mutated=bytearray(DATA)
    for _ in range(fuzz.randint(1,4)):
        mutated[fuzz.randrange(len(mutated))]=fuzz.randrange(256)
    inspect(bytes(mutated))  # Malformed data cannot escape as exceptions or approval.

# Specified arithmetic vectors, including zero/overflow and line-border ownership.
BASE=64<<30
def ranges(offset,size,**kwargs):
    return v.review_range(kwargs.get('owned_start',BASE),kwargs.get('owned_bytes',4096),
                          BASE+offset,size,kwargs.get('line',64))
assert ranges(0,0)['status']=='NOOP' and not ranges(0,0)['line_count']
for offset,size,expected in ((1,63,[BASE,BASE+64]),(63,2,[BASE,BASE+128]),(4080,16,[BASE+4032,BASE+4096])):
    assert ranges(offset,size)['rounded_interval']==expected
for offset,size in ((4080,17),(-1,1),(4090,20)):
    assert ranges(offset,size)['status']=='REJECT'
assert ranges(1,1,owned_start=BASE+1,owned_bytes=4095)['status']=='REJECT'
for args in ((v.U64_MAX-31,64,v.U64_MAX-31,1,64),(0,v.U64_MAX,v.U64_MAX-31,1,64),
             (0,4096,0,True,64),(0,4096,0,1,0),(0,4096,0,1,48)):
    assert v.review_range(*args)['status']=='REJECT'
assert ranges(0,1,line=512)['status']=='PENDING'
rng=random.Random(191126)
for _ in range(500):
    start=rng.randrange(5000);size=rng.randrange(200)
    got=ranges(start,size)
    if not size: assert got['status']=='NOOP'
    else:
        lo=start//64*64;hi=(start+size+63)//64*64
        assert got['status']==('PASS' if hi<=4096 else 'REJECT')
        if got['status']=='PASS': assert got['line_count']==(hi-lo)//64

# Historical artifact is a negative PAC control, never a full positive candidate.
root=Path(__file__).resolve().parents[2]
historical=v.inspect_bytes((root/'quest3/module/quest_kexec.ko').read_bytes())
assert historical['overall']=='REJECT' and historical['checks']['L08']['status']=='REJECT'
assert historical['observations']['direct_calls_observed']==3

with tempfile.TemporaryDirectory(prefix='cache-leaf-review-',dir=root/'.work') as temp:
    path=Path(temp)/'synthetic.elf';path.write_bytes(DATA)
    completed=subprocess.run([sys.executable,str(Path(v.__file__)),str(path),'--symbol',NAME],capture_output=True,text=True,timeout=20)
    assert completed.returncode==2 and json.loads(completed.stdout)['overall']=='PENDING'
    assert path.read_bytes()==DATA
    negative=fixture((BTI,RET));path.write_bytes(negative)
    completed=subprocess.run([sys.executable,str(Path(v.__file__)),str(path),'--symbol',NAME],capture_output=True,text=True,timeout=20)
    assert completed.returncode==1 and json.loads(completed.stdout)['overall']=='REJECT'
    assert path.read_bytes()==negative
print('PASS read-only static leaf subset: bounded ELF/relocations, BTI/registers/PAC CFG, escapes/unknowns, uint64 range vectors and historical PAC rejection; no helper approval or executed bytes')
