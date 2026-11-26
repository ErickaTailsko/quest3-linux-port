#!/usr/bin/env python3
"""Pure HOST import/content consistency. No files, loader, build or device calls.

A matching explicit policy/hash set is caller-supplied metadata, NOT trusted
build provenance or authorization. Overall output is only PENDING or REJECT.
This module does not replace the separate leaf/PAC/call-graph verifier.
"""
from dataclasses import asdict,dataclass
import hashlib
import json
import re
import struct

import cache_leaf_static_review as leaf
from relocation_plan import flags

PROFILE='q3-cache-leaf-import-review-host-v1'
MAX_SYMVERS_BYTES=8*1024*1024
MAX_EXPORTS=65536
MAX_IMPORTS=1024
MAX_MODINFO_BYTES=65536
KINDS=('EXPORT_SYMBOL','EXPORT_SYMBOL_GPL','EXPORT_SYMBOL_GPL_FUTURE',
       'EXPORT_UNUSED_SYMBOL','EXPORT_UNUSED_SYMBOL_GPL')


@dataclass(frozen=True)
class ImportRule:
    name: str
    crc: int
    provider: str
    kind: str
    namespace: str = ''


def _identifier(text,empty=False):
    return type(text) is str and ((empty and text=='') or re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',text))


def _rule(rule):
    if (type(rule) is not ImportRule or not _identifier(rule.name) or
            type(rule.crc) is not int or not 0<=rule.crc<=0xffffffff or
            type(rule.provider) is not str or not re.fullmatch('[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+)*',rule.provider) or
            len(rule.provider)>256 or any(x in ('.','..') for x in rule.provider.split('/')) or
            type(rule.kind) is not str or rule.kind not in KINDS or not _identifier(rule.namespace,True)):
        raise ValueError('invalid typed import rule')
    return rule


def policy_sha256(policy):
    if type(policy) is not tuple or not 1<=len(policy)<=MAX_IMPORTS:
        raise ValueError('bounded explicit immutable import policy required')
    for rule in policy: _rule(rule)
    if len({x.name for x in policy})!=len(policy): raise ValueError('duplicate import policy name')
    canonical=json.dumps([asdict(x) for x in sorted(policy,key=lambda x:x.name)],sort_keys=True,separators=(',',':'))
    return hashlib.sha256(b'Q3-LEAF-IMPORT-POLICY-V1\0'+(canonical+'\n').encode('ascii')).hexdigest()


def _exports(blob):
    if type(blob) is not bytes or not 0<len(blob)<=MAX_SYMVERS_BYTES:
        raise ValueError('bounded immutable symvers bytes required')
    try: text=blob.decode('ascii')
    except UnicodeDecodeError: raise ValueError('ASCII symvers required')
    lines=text.splitlines()
    if not 1<=len(lines)<=MAX_EXPORTS: raise ValueError('symvers row limit')
    result={}
    for line in lines:
        if len(line)>512: raise ValueError('symvers row length limit')
        row=line.split('\t')
        if len(row) not in (4,5) or not re.fullmatch('0x[0-9a-fA-F]{8}',row[0]):
            raise ValueError('explicit CRC/provider/kind/namespace symvers row required')
        crc,name,provider,kind=row[:4];namespace=row[4] if len(row)==5 else ''
        rule=_rule(ImportRule(name,int(crc,16),provider,kind,namespace))
        if name in result: raise ValueError('duplicate stock export')
        result[name]=rule
    return result


def _records(blob,parsed):
    sections={}
    for name,h in zip(parsed['section_names'],parsed['section_headers']):
        if name not in ('__versions','.modinfo'): continue
        if name in sections or h[1]!=1: raise ValueError('duplicate/non-PROGBITS module metadata')
        sections[name]=blob[h[4]:h[4]+h[5]]
    if not sections: return None
    if set(sections)!= {'__versions','.modinfo'}: raise ValueError('incomplete MODVERSIONS metadata pair')
    data=sections['__versions']
    if not data or len(data)%64 or len(data)//64>MAX_IMPORTS:
        raise ValueError('bounded ARM64 64-byte version records required')
    versions={}
    for offset in range(0,len(data),64):
        crc=struct.unpack_from('<Q',data,offset)[0];raw=data[offset+8:offset+64]
        end=raw.find(b'\0')
        if end<1 or crc>0xffffffff or any(raw[end+1:]): raise ValueError('invalid version name/CRC/padding')
        try: name=raw[:end].decode('ascii')
        except UnicodeDecodeError: raise ValueError('ASCII import name required')
        if not _identifier(name) or name in versions: raise ValueError('duplicate/invalid version symbol')
        versions[name]=crc
    data=sections['.modinfo']
    if not data or len(data)>MAX_MODINFO_BYTES or data[-1]: raise ValueError('bounded terminated modinfo required')
    info={};rows=data.split(b'\0')
    if len([x for x in rows if x])>MAX_IMPORTS: raise ValueError('modinfo row limit')
    for row in rows:
        if not row: continue
        if len(row)>1024: raise ValueError('modinfo row length limit')
        try: text=row.decode('ascii')
        except UnicodeDecodeError: raise ValueError('ASCII modinfo required')
        key,sep,value=text.partition('=')
        if not sep or not _identifier(key) or any(ord(c)<32 or ord(c)>126 for c in value):
            raise ValueError('invalid modinfo key/value')
        info.setdefault(key,[]).append(value)
    for key in ('license','depends'):
        if len(info.get(key,[]))!=1: raise ValueError('one explicit license/depends metadata record required')
    namespaces=info.get('import_ns',[])
    if len(set(namespaces))!=len(namespaces) or any(not _identifier(x) for x in namespaces):
        raise ValueError('duplicate/invalid import namespace')
    dependencies=info['depends'][0].split(',') if info['depends'][0] else []
    if (len(set(dependencies))!=len(dependencies) or
            any(not re.fullmatch('[A-Za-z0-9_-]{1,128}',x) for x in dependencies)):
        raise ValueError('duplicate/invalid dependency metadata')
    undefined=[s['name'] for s in parsed['symbol_records'] if not s['section'] and s['name']]
    if len(set(undefined))!=len(undefined): raise ValueError('duplicate undefined ELF symbol')
    if 'module_layout' not in versions or set(versions)!=set(undefined)|{'module_layout'}:
        raise ValueError('versions must equal undefined symbols plus module_layout')
    return versions,info,set(dependencies)


def review(elf_bytes,symvers_bytes,policy=None,*,expected_hashes=None,symbol='qkx_flush_dcache_area'):
    """Check only bytes, stock-table agreement and an explicit caller-supplied policy.

    No policy is inferred from the ELF. Missing policy/hashes stay PENDING.
    A forged but internally consistent bundle still cannot prove build or grant
    runtime admission. GPL/dependency checks use a deliberately narrow profile.
    """
    checks={name:dict(status='PENDING',reason='evidence not supplied') for name in
            ('elf_metadata','stock_table','interface_match','explicit_policy','content_binding')}
    if type(expected_hashes) is dict: expected_hashes=expected_hashes.copy()
    observations={};digests={};stage='elf_metadata'
    try:
        parsed=leaf._elf(elf_bytes,symbol)
        digests['elf']=hashlib.sha256(elf_bytes).hexdigest()
        records=_records(elf_bytes,parsed)
        if records is None:
            checks[stage]=dict(status='PENDING',reason='module metadata absent; no import conclusion')
        else: checks[stage]=dict(status='PASS',reason='bounded metadata and exact undefined/version relation')
        stage='stock_table';exports=_exports(symvers_bytes)
        digests['symvers']=hashlib.sha256(symvers_bytes).hexdigest()
        checks[stage]=dict(status='PASS',reason='bounded unique explicit stock export rows')
        stage='explicit_policy'
        if policy is not None:
            digests['policy']=policy_sha256(policy)
            if records is None:
                checks[stage]=dict(status='PENDING',reason='policy supplied but module metadata absent')
        stage='content_binding'
        if expected_hashes is not None:
            if (type(expected_hashes) is not dict or set(expected_hashes)!={'elf','symvers','policy'} or
                    any(type(x) is not str or not re.fullmatch('[0-9a-f]{64}',x) for x in expected_hashes.values())):
                raise ValueError('exact three content hashes required; no partial/extra bindings')
            if digests!=expected_hashes: raise ValueError('ELF/table/policy content substitution')
            checks[stage]=dict(status='PASS',reason='bytes match caller-supplied hashes only; NOT build attestation')
        if records is not None:
            versions,info,dependencies=records;stage='interface_match';rows=[]
            modules={}
            for name,crc in sorted(versions.items()):
                if name not in exports or exports[name].crc!=crc: raise ValueError('missing stock export or CRC mismatch: '+name)
                rule=exports[name]
                if rule.namespace and rule.namespace not in info.get('import_ns',[]):
                    raise ValueError('required namespace not declared: '+name)
                if 'GPL' in rule.kind and info['license'][0] not in ('GPL','GPL v2','Dual BSD/GPL','Dual MIT/GPL'):
                    raise ValueError('GPL export with unsupported/incompatible license')
                if rule.provider!='vmlinux':
                    module=rule.provider.rsplit('/',1)[-1]
                    if module in modules and modules[module]!=rule.provider:
                        raise ValueError('ambiguous providers share one dependency name')
                    modules[module]=rule.provider
                rows.append(asdict(rule))
            if set(modules)!=dependencies: raise ValueError('modular providers and depends metadata differ')
            observations.update(versions=len(versions),undefined=len(parsed['undefined']),imports=rows,
                import_namespaces=info.get('import_ns',[]),dependencies=sorted(dependencies),license=info['license'][0])
            checks[stage]=dict(status='PASS',reason='recorded CRC/provider/namespace/license/dependency consistency only')
            stage='explicit_policy'
            if policy is not None:
                by_name={x.name:x for x in policy}
                if set(by_name)!=set(versions): raise ValueError('explicit policy missing/extra import')
                for name in versions:
                    if by_name[name]!=exports[name]: raise ValueError('explicit policy CRC/provider/kind/namespace mismatch: '+name)
                checks[stage]=dict(status='PASS',reason='exact match to caller-supplied policy, NOT authorization')
    except (ValueError,struct.error) as error:
        checks[stage]=dict(status='REJECT',reason=str(error))
    return dict(profile=PROFILE,scope='HOST content/import consistency only; NOT build, ABI/CFI, cache or lifetime proof',
        overall='REJECT' if any(x['status']=='REJECT' for x in checks.values()) else 'PENDING',
        metadata_consistent=all(x['status']=='PASS' for x in checks.values()),
        checks=checks,input_sha256=digests,observations=observations,
        source_to_binary_build_relation_proven=False,full_c_abi_verified=False,leaf_contract_evaluated=False,
        helper_approved=False,runtime_admission_enabled=False,authorization_verified=False,
        cache_protocol_verified=False,actual_lifetime_proven=False,inspected_bytes_executed=False,**flags())
