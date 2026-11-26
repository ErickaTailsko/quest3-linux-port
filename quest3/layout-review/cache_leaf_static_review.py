#!/usr/bin/env python3
"""Read-only HOST subset verifier. Never execute inspected ELF/instructions.

PASS is per static obligation only. Overall approval is never produced: source
provenance, C ABI, platform cache semantics and lifetime remain PENDING.
"""
import hashlib
import heapq
import json
import re
import struct

from relocation_plan import flags

PROFILE='q3-cache-leaf-static-review-host-v1'
MAX_BYTES=32*1024*1024
MAX_SECTIONS=512
MAX_SYMBOLS=65536
MAX_RELOCS=65536
MAX_INSNS=4096
MAX_CFG_STATES=32768
MAX_STRING=1024
MAX_NAME_SCAN_BYTES=4*1024*1024
U64_MAX=(1<<64)-1


def _caller_map(symbols,queries):
    """Sweep queried call sites once; preserve ambiguity, avoid symbols x relocations."""
    functions={}
    for index,s in enumerate(symbols):
        if s['info']&15==2 and s['size'] and not s['value']%4 and not s['size']%4:
            functions.setdefault(s['section'],[]).append((s['value'],s['value']+s['size'],index))
    grouped={}
    for section,offset in queries: grouped.setdefault(section,set()).add(offset)
    result={}
    for section,offsets in grouped.items():
        ordered=sorted(functions.get(section,()));cursor=0;ends=[];active=set()
        for offset in sorted(offsets):
            while cursor<len(ordered) and ordered[cursor][0]<=offset:
                _,end,index=ordered[cursor];heapq.heappush(ends,(end,index));active.add(index);cursor+=1
            while ends and ends[0][0]<offset+4:
                _,index=heapq.heappop(ends);active.remove(index)
            result[(section,offset)]=symbols[next(iter(active))]['name'] if len(active)==1 else None
    return result


def _result(checks,observations):
    return dict(profile=PROFILE,scope='read-only static subset, NOT helper approval or runtime evidence',
        overall='REJECT' if any(v['status']=='REJECT' for v in checks.values()) else 'PENDING',
        checks=checks,observations=observations,helper_approved=False,
        runtime_admission_enabled=False,authorization_verified=False,
        cache_protocol_verified=False,actual_lifetime_proven=False,
        inspected_bytes_executed=False,**flags())


def review_range(owned_start,owned_bytes,start,size,line):
    """Unsigned-64 arithmetic only; arguments do NOT prove ownership or CPU line size."""
    result=dict(profile=PROFILE,scope='host arithmetic only; no mapping or ownership verification',
        status='REJECT',reason='invalid uint64 input or line',rounded_interval=None,line_count=0,
        helper_called=False,ownership_acquired=False,cache_protocol_verified=False,boot_ready=False)
    if (any(type(x) is not int or not 0<=x<=U64_MAX for x in (owned_start,owned_bytes,start,size,line)) or
            not owned_bytes or not line or line&(line-1)):
        return result
    if line not in (16,32,64,128,256):
        return dict(result,status='PENDING',reason='power-of-two line outside reviewed assumption profile')
    if owned_start+owned_bytes>U64_MAX:
        return dict(result,reason='owned extent end overflows uint64')
    if not size:
        return dict(result,status='NOOP',reason='empty request; no maintenance or publication claimed')
    end=start+size
    if end>U64_MAX: return dict(result,reason='request end overflows uint64')
    lo=start//line*line;hi=(end+line-1)//line*line
    if hi>U64_MAX: return dict(result,reason='rounded end overflows uint64')
    if not owned_start<=lo<hi<=owned_start+owned_bytes:
        return dict(result,reason='rounded request outside one declared extent')
    return dict(result,status='PASS',reason='arithmetic fits one declared extent only',
                rounded_interval=[lo,hi],line_count=(hi-lo)//line)


def _elf(data,name):
    if type(data) is not bytes or not 64<=len(data)<=MAX_BYTES:
        raise ValueError('bounded immutable ELF bytes required')
    if type(name) is not str or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',name):
        raise ValueError('bounded explicit function symbol required')
    def unpack(fmt,offset):
        size=struct.calcsize(fmt)
        if not 0<=offset<=len(data)-size: raise ValueError('truncated ELF record')
        return struct.unpack_from(fmt,data,offset)
    h=unpack('<16sHHIQQQIHHHHHH',0)
    if (h[0][:7]!=b'\x7fELF\x02\x01\x01' or h[1]!=1 or h[2]!=183 or h[3]!=1 or
            h[4] or h[5] or h[8]!=64 or h[10] or h[11]!=64 or
            not 1<h[12]<=MAX_SECTIONS or not 0<h[13]<h[12] or h[6]<64 or
            h[6]>len(data)-h[12]*64):
        raise ValueError('only bounded ELF64 LE AArch64 REL without program headers/extended numbering')
    sections=[unpack('<IIQQQQIIQQ',h[6]+i*64) for i in range(h[12])]
    if sections[0]!=(0,)*10: raise ValueError('null section required')
    regions=[(0,64),(h[6],h[6]+len(sections)*64)]
    for sec in sections[1:]:
        if sec[2]&0x800: raise ValueError('compressed sections outside parser profile')
        if sec[8] and sec[8]&(sec[8]-1): raise ValueError('invalid section alignment')
        if sec[1]!=8 and sec[5]:
            if sec[4]<64 or sec[4]>len(data)-sec[5]: raise ValueError('section file bounds')
            regions.append((sec[4],sec[4]+sec[5]))
    regions.sort()
    if any(a[1]>b[0] for a,b in zip(regions,regions[1:])):
        raise ValueError('overlapping file sections/header tables')
    string_cache={};name_scan_bytes=0
    def string(sec,offset):
        nonlocal name_scan_bytes
        if sec[1]!=3 or not 0<=offset<sec[5]: raise ValueError('string table bounds/type')
        key=(sec[4],sec[5],offset)
        if key in string_cache: return string_cache[key]
        start=sec[4]+offset
        end=data.find(b'\0',start,min(sec[4]+sec[5],start+MAX_STRING+1))
        if end<0: raise ValueError('unterminated or over-limit ELF string')
        name_scan_bytes+=end-start+1
        if name_scan_bytes>MAX_NAME_SCAN_BYTES: raise ValueError('total ELF name scan budget exceeded')
        try: result=data[start:end].decode('ascii')
        except UnicodeDecodeError: raise ValueError('non-ASCII string outside parser profile')
        string_cache[key]=result
        return result
    names=[string(sections[h[13]],sec[0]) for sec in sections]
    tabs=[i for i,sec in enumerate(sections) if sec[1]==2]
    if len(tabs)!=1: raise ValueError('exactly one symbol table required for reference coverage')
    tab_index=tabs[0];tab=sections[tab_index]
    if (tab[9]!=24 or not tab[5] or tab[5]%24 or tab[5]//24>MAX_SYMBOLS or
            not 0<tab[6]<len(sections) or sections[tab[6]][1]!=3):
        raise ValueError('symbol table shape/link/limit')
    symbols=[]
    for i in range(tab[5]//24):
        row=unpack('<IBBHQQ',tab[4]+i*24)
        sym_name=string(sections[tab[6]],row[0])
        if row[3]==0xffff: raise ValueError('extended symbol section index unsupported')
        if 0<row[3]<0xff00:
            if row[3]>=len(sections) or row[4]>sections[row[3]][5] or row[5]>sections[row[3]][5]-row[4]:
                raise ValueError('defined symbol outside section bounds')
        symbols.append(dict(name=sym_name,info=row[1],section=row[3],value=row[4],size=row[5]))
    matches=[(i,s) for i,s in enumerate(symbols) if s['name']==name]
    if len(matches)!=1: raise ValueError('missing/ambiguous helper symbol')
    symbol_index,sym=matches[0];ndx=sym['section']
    if (sym['info']&15!=2 or not 0<ndx<len(sections) or sym['value']%4 or
            not 0<sym['size']<=MAX_INSNS*4 or sym['size']%4):
        raise ValueError('bounded aligned STT_FUNC helper required')
    text=sections[ndx]
    if text[1]!=1 or text[2]&6!=6 or text[2]&1 or text[8]<4 or sym['value']>text[5]-sym['size']:
        raise ValueError('helper outside non-writable allocated executable PROGBITS')
    lo=sym['value'];hi=lo+sym['size']
    for i,other in enumerate(symbols):
        if i==symbol_index or other['section']!=ndx or not other['name']: continue
        kind=other['info']&15;binding=other['info']>>4
        overlap=(other['value']<hi and lo<other['value']+other['size']) if other['size'] else lo<=other['value']<hi
        if overlap and other['name'].startswith('$d'):
            raise ValueError('data mapping symbol inside narrow code-only leaf')
        if overlap and (kind==2 or (kind==0 and binding in (1,2))):
            raise ValueError('overlapping function/global alias into helper')
    references=[];relocs=[];total=0;pending_calls=[]
    for sec in sections:
        if sec[1]==9: raise ValueError('SHT_REL unsupported; cannot silently omit relocations')
        if sec[1]!=4: continue
        if (sec[9]!=24 or sec[5]%24 or sec[6]!=tab_index or not 0<sec[7]<len(sections)):
            raise ValueError('RELA shape/link/target')
        total+=sec[5]//24
        if total>MAX_RELOCS: raise ValueError('relocation limit exceeded')
        target=sections[sec[7]]
        for i in range(sec[5]//24):
            offset,info,addend=unpack('<QQq',sec[4]+i*24)
            si=info>>32;typ=info&0xffffffff
            if si>=len(symbols) or offset>=target[5]: raise ValueError('relocation symbol/target bounds')
            if offset+{257:8,258:4,261:4,282:4,283:4}.get(typ,1)>target[5]:
                raise ValueError('known relocation field crosses target bounds')
            relocation=dict(target_section=sec[7],offset=offset,type=typ,symbol_index=si,addend=addend)
            relocs.append(relocation)
            via_section=(symbols[si]['info']&15==3 and symbols[si]['section']==ndx and
                         lo<=symbols[si]['value']+addend<hi)
            via_other=(si!=symbol_index and symbols[si]['section']==ndx and
                       lo<=symbols[si]['value']+addend<hi)
            if si!=symbol_index and not via_other: continue
            ref=dict(section=names[sec[7]],offset=offset,type=typ,addend=addend,
                     via_section_symbol=via_section,via_other_symbol=via_other,classification='unreviewed')
            if target[2]&4:
                if target[1]!=1: raise ValueError('executable reference target is not PROGBITS')
                if offset%4 or offset>target[5]-4: raise ValueError('call-site bounds/alignment')
                word=unpack('<I',target[4]+offset)[0]
                if typ==283 and word&0xfc000000==0x94000000 and not addend and not via_other:
                    pending_calls.append((ref,sec[7],offset))
            elif not target[2]&2 and names[sec[7]].startswith('.debug'):
                ref['classification']='nonallocated-debug-reference'
            else:
                ref['classification']='address-escape-or-unreviewed-data'
            references.append(ref)
    callers=_caller_map(symbols,{(section,offset) for _,section,offset in pending_calls})
    for ref,section,offset in pending_calls:
        caller=callers[(section,offset)]
        if caller is not None: ref.update(classification='direct-call-observed',caller=caller)
    # All relocations in the body must be understood before decoding final words.
    body_relocs=[x for x in relocs if x['target_section']==ndx and lo<=x['offset']<hi]
    raw=data[text[4]+lo:text[4]+hi]
    return dict(words=struct.unpack('<'+'I'*(len(raw)//4),raw),references=references,
                body_relocations=body_relocs,undefined=sorted({s['name'] for s in symbols if not s['section'] and s['name']}),
                symbol_bytes=sym['size'],section=names[ndx],symbol=name,
                section_headers=sections,section_names=names,symbol_records=symbols,
                parser_metrics=dict(symbols=len(symbols),relocations=total,unique_call_sites=len(callers),
                                    unique_strings=len(string_cache),name_bytes_scanned=name_scan_bytes))


def _signed(value,bits): return value-(1<<bits) if value&(1<<(bits-1)) else value


def _decode(word,pc):
    fixed={0xd503245f:'bti',0xd503201f:'nop',0xd503233f:'sign-a',0xd503237f:'sign-b',
           0xd50323bf:'auth-a',0xd50323ff:'auth-b',0xd65f03c0:'ret',
           0xd65f0bff:'retaa',0xd65f0fff:'retab',0xd5033f9f:'dsb-sy'}
    if word in fixed: return (fixed[word],None)
    def registers(*regs):
        return ('register-violation',None) if any(x not in (0,1,2,3,31) for x in regs) else ('alu',None)
    if word&0xfc000000==0x94000000: return ('nested-call',None)
    if word&0xfe000000==0xd6000000: return ('indirect-control',None)
    if word&0xfc000000==0x14000000: return ('branch',pc+_signed(word&0x3ffffff,26)*4)
    if word&0xff000010==0x54000000:
        if word&15>=14: return ('unknown',None)
        return ('conditional',pc+_signed((word>>5)&0x7ffff,19)*4)
    if word&0x7e000000==0x34000000:
        if not word&0x80000000 or word&31 not in (0,1,2,3): return ('register-violation',None)
        return ('conditional',pc+_signed((word>>5)&0x7ffff,19)*4)
    if word&0xffffffe0==0xd53b0020:
        return ('ctr',None) if word&31 in (0,1,2,3) else ('register-violation',None)
    for mask_value,kind in ((0xd50b7e20,'poc'),(0xd50b7a20,'poc'),(0xd50b7b20,'pou'),(0xd5087620,'invalidate-only')):
        if word&0xffffffe0==mask_value:
            return (kind,None) if word&31 in (0,1,2,3) else ('register-violation',None)
    rd=word&31;rn=(word>>5)&31;rm=(word>>16)&31
    if word&0x80000000 and word&0x1f800000==0x11000000:  # ADD/SUB immediate; 31 means SP.
        if rn==31 or (rd==31 and not word&(1<<29)): return ('register-violation',None)
        return registers(rd,rn)
    if word&0x80000000 and word&0x1f200000==0x0b000000:  # Shifted ADD/SUB; 31 means ZR.
        if (word>>22)&3==3: return ('unknown',None)
        return registers(rd,rn,rm)
    if word&0x80000000 and word&0x1f000000==0x0a000000: return registers(rd,rn,rm)
    if word&0xffc00000==0xd3400000: return registers(rd,rn)  # UBFM aliases.
    if word&0xff800000==0xd2800000: return registers(rd)  # MOVZ.
    if word&0xffe0fc00==0x9ac02000: return registers(rd,rn,rm)  # LSLV.
    if word&0xff000000==0xd5000000: return ('unreviewed-system',None)
    return ('unknown',None)


def inspect_bytes(data,*,symbol='qkx_flush_dcache_area'):
    checks={f'L{i:02d}':dict(status='PENDING',reason='not established by this static subset') for i in range(1,15)}
    observations={}
    def mark(key,status,reason):
        if checks[key]['status']!='REJECT': checks[key]=dict(status=status,reason=reason)
    try: elf=_elf(data,symbol)
    except (ValueError,struct.error) as error:
        mark('L09','REJECT',str(error));return _result(checks,observations)
    observations.update(sha256=hashlib.sha256(data).hexdigest(),symbol=symbol,
        symbol_bytes=elf['symbol_bytes'],section=elf['section'],references=elf['references'],undefined_symbols=elf['undefined'],
        parser_metrics=elf['parser_metrics'])
    mark('L09','PASS','bounded ELF/function/relocation structure in supported REL profile')
    for ref in elf['references']:
        if ref['classification']=='address-escape-or-unreviewed-data':
            mark('L04','REJECT','helper address referenced from allocated/unreviewed data')
        elif ref['classification']=='unreviewed':
            mark('L03','REJECT','executable helper reference is not a reviewed direct CALL26')
            mark('L04','REJECT','executable address reference remains unreviewed')
    # Whole-caller ABI/control flow and source integrity are deliberately not inferred.
    observations['direct_calls_observed']=sum(x['classification']=='direct-call-observed' for x in elf['references'])
    if set(elf['undefined']).intersection(('register_kprobe','unregister_kprobe','kallsyms_lookup_name')):
        mark('L10','REJECT','private resolver imports outside contract')
    decoded=[_decode(w,pc*4) for pc,w in enumerate(elf['words'])]
    observations['decoded_kinds']=[x[0] for x in decoded]
    if decoded[0][0]=='bti': mark('L06','PASS','explicit BTI c at function entry')
    else: mark('L06','REJECT','entry is not explicit BTI c')
    bad={kind for kind,_ in decoded}
    if 'register-violation' in bad: mark('L07','REJECT','register or SP use outside narrow leaf profile')
    if bad.intersection(('nested-call','indirect-control')):
        mark('L03','REJECT','nested/indirect control transfer in helper')
        mark('L13','REJECT','helper is not a closed direct-call leaf')
    if 'unreviewed-system' in bad: mark('L13','REJECT','system instruction outside reviewed subset')
    if 'pou' in bad or 'invalidate-only' in bad:
        mark('L12','REJECT','PoU-only/invalidate operation outside PoC leaf subset')
    unknown='unknown' in bad or bool(elf['body_relocations'])
    if unknown:
        mark('L09','PENDING','ELF bounds checked; unknown opcode or unresolved relocation inside body')
        observations['body_relocations']=elf['body_relocations']
        return _result(checks,observations)
    unsafe=bad.intersection(('register-violation','nested-call','indirect-control','unreviewed-system'))
    if unsafe: return _result(checks,observations)
    mark('L07','PASS','all decoded words preserve x18/callee-saved/SP; LR only PAC/return')
    mark('L13','PASS','closed decoded subset has no calls, memory loads/stores, I/O or context writes')
    # Abstract control-flow traversal only; no register values or instructions execute.
    todo=[(0,'unsigned',False)];seen=set();returns=0;size=len(decoded)*4;finished=True
    while todo:
        pc,pac,dirty=todo.pop()
        if (pc,pac,dirty) in seen: continue
        if len(seen)>=MAX_CFG_STATES:
            mark('L08','PENDING','control-flow state bound exceeded');finished=False;break
        if pc%4 or not 0<=pc<size:
            mark('L08','REJECT','branch/fallthrough outside helper')
            mark('L07','PENDING','control escapes inspected body')
            mark('L13','REJECT','control escapes inspected body');continue
        seen.add((pc,pac,dirty));kind,target=decoded[pc//4]
        if kind.startswith('sign-'):
            if pac!='unsigned': mark('L08','REJECT','PAC signing state overwritten');continue
            pac='signed-'+kind[-1]
        elif kind.startswith('auth-'):
            if pac!='signed-'+kind[-1]: mark('L08','REJECT','PAC authentication missing/mismatched');continue
            pac='authenticated-'+kind[-1]
        elif kind in ('ret','retaa','retab'):
            returns+=1
            valid=pac.startswith('authenticated-') if kind=='ret' else pac=='signed-'+kind[-1]
            if not valid: mark('L08','REJECT','reachable return lacks matching PAC protection')
            if dirty: mark('L12','REJECT','reachable return after cache op without subsequent DSB SY')
            continue
        elif kind in ('poc','pou','invalidate-only'): dirty=True
        elif kind=='dsb-sy': dirty=False
        if kind=='branch': todo.append((target,pac,dirty))
        elif kind=='conditional': todo.extend(((target,pac,dirty),(pc+4,pac,dirty)))
        else: todo.append((pc+4,pac,dirty))
    observations.update(cfg_states=len(seen),reachable_returns=returns)
    if finished and not todo and returns and checks['L08']['status']!='REJECT':
        mark('L08','PASS','all statically reachable returns use matching SP-based PAC in decoded subset')
    # Even a PAC/ABI pass does not establish ranges, termination, errata or PoC.
    return _result(checks,observations)


if __name__=='__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf')
    parser.add_argument('--symbol',default='qkx_flush_dcache_area')
    args=parser.parse_args()
    try:
        if not Path(args.elf).is_file(): parser.exit(2,'regular local ELF file required\n')
        with open(args.elf,'rb') as stream: data=stream.read(MAX_BYTES+1)
        report=inspect_bytes(data,symbol=args.symbol)
    except OSError as error:
        parser.exit(2,str(error)+'\n')
    print(json.dumps(report,indent=2))
    raise SystemExit(1 if report['overall']=='REJECT' else 2)
