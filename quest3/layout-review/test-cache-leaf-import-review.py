#!/usr/bin/env python3
"""Unlinked metadata fixtures only: no module build/load or inspected execution."""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

import cache_leaf_import_review as v
import cache_leaf_static_review as leaf
from relocation_plan import flags

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('import_fixture_cases',here/'test-cache-leaf-static-review.py')
cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)
NAME=cases.NAME
IMPORTS=(('fixture_api',1),('fixture_scm',2))
POLICY=(v.ImportRule('fixture_api',1,'vmlinux','EXPORT_SYMBOL'),
        v.ImportRule('fixture_scm',2,'drivers/fixture-scm','EXPORT_SYMBOL_GPL','FIXTURE_NS'),
        v.ImportRule('module_layout',3,'vmlinux','EXPORT_SYMBOL'))
SYMVERS=b'0x00000001\tfixture_api\tvmlinux\tEXPORT_SYMBOL\t\n0x00000002\tfixture_scm\tdrivers/fixture-scm\tEXPORT_SYMBOL_GPL\tFIXTURE_NS\n0x00000003\tmodule_layout\tvmlinux\tEXPORT_SYMBOL\t\n'
INFO=b'license=GPL\0depends=fixture-scm\0import_ns=FIXTURE_NS\0'


def fixture(*,undefined=IMPORTS,versions=None,info=INFO,duplicate_metadata=False,raw_versions=None,omit=None):
    """Attach invented interface records to an unlinked non-module ELF fixture."""
    base=cases.fixture();p=leaf._elf(base,NAME);specs=[]
    for name,h in zip(p['section_names'],p['section_headers']):
        if name=='.shstrtab': continue
        specs.append((name,h[1],h[2],base[h[4]:h[4]+h[5]],h[6],h[7],h[8],h[9]))
    strings=bytearray(specs[2][3]);symbols=bytearray(specs[3][3])
    for name,_ in undefined:
        offset=len(strings);strings.extend(name.encode()+b'\0')
        symbols.extend(struct.pack('<IBBHQQ',offset,0x12,0,0,0,0))
    specs[2]=(*specs[2][:3],bytes(strings),*specs[2][4:])
    specs[3]=(*specs[3][:3],bytes(symbols),*specs[3][4:])
    if versions is None: versions=(*IMPORTS,('module_layout',3))
    records=raw_versions
    if records is None:
        records=b''.join(struct.pack('<Q',crc)+name.encode().ljust(56,b'\0') for name,crc in versions)
    specs.extend(row for row in (('__versions',1,2,records,0,0,8,0),('.modinfo',1,2,info,0,0,1,0)) if row[0]!=omit)
    if duplicate_metadata: specs.append(('.modinfo',1,2,info,0,0,1,0))
    names=b'\0';offsets={'':0}
    for name,*_ in specs[1:]:
        if name not in offsets: offsets[name]=len(names);names+=name.encode()+b'\0'
    offsets['.shstrtab']=len(names);names+=b'.shstrtab\0'
    specs.append(('.shstrtab',3,0,names,0,0,1,0))
    blob=bytearray(64);headers=[]
    for name,typ,fl,data,link,section_info,align,entsize in specs:
        if not typ: headers.append((0,)*10);continue
        blob.extend(bytes((-len(blob))%max(align,1)));offset=len(blob);blob.extend(data)
        headers.append((offsets[name],typ,fl,0,offset,len(data),link,section_info,align,entsize))
    blob.extend(bytes((-len(blob))%8));shoff=len(blob)
    for header in headers: blob.extend(struct.pack('<IIQQQQIIQQ',*header))
    struct.pack_into('<16sHHIQQQIHHHHHH',blob,0,b'\x7fELF\x02\x01\x01'+bytes(9),
                     1,183,1,0,0,shoff,0,64,0,0,64,len(headers),len(headers)-1)
    return bytes(blob)


def pins(blob= None,table=SYMVERS,policy=POLICY):
    return dict(elf=hashlib.sha256(DATA if blob is None else blob).hexdigest(),
                symvers=hashlib.sha256(table).hexdigest(),policy=v.policy_sha256(policy))


def review(blob=None,table=SYMVERS,policy=POLICY,**kwargs):
    report=v.review(DATA if blob is None else blob,table,policy,symbol=NAME,**kwargs)
    for field in (*flags(),'source_to_binary_build_relation_proven','full_c_abi_verified','leaf_contract_evaluated',
                  'helper_approved','runtime_admission_enabled','authorization_verified','cache_protocol_verified',
                  'actual_lifetime_proven','inspected_bytes_executed'):
        assert report[field] is False
    assert report['overall'] in ('PENDING','REJECT')
    return report


def rejected(*args,**kwargs):
    report=review(*args,**kwargs)
    assert report['overall']=='REJECT' and not report['metadata_consistent'],report


DATA=fixture()
MATCHED=review(expected_hashes=pins())
assert MATCHED['metadata_consistent'] and MATCHED['overall']=='PENDING'
assert MATCHED['observations']['versions']==3 and MATCHED['observations']['undefined']==2
assert not review()['metadata_consistent'] and review()['checks']['content_binding']['status']=='PENDING'
assert review(policy=None)['checks']['explicit_policy']['status']=='PENDING'
assert review(cases.fixture())['checks']['elf_metadata']['status']=='PENDING'
rejected(fixture(omit='__versions'));rejected(fixture(omit='.modinfo'))
assert v.policy_sha256(tuple(reversed(POLICY)))==v.policy_sha256(POLICY)
for policy in (list(POLICY),(),POLICY+POLICY[:1],POLICY[:-1],POLICY+(v.ImportRule('extra',7,'vmlinux','EXPORT_SYMBOL'),)):
    rejected(policy=policy)
for field,value in (('crc',True),('provider','../bad'),('kind','unknown'),('namespace','bad ns'),('name','')):
    rejected(policy=(replace(POLICY[0],**{field:value}),)+POLICY[1:])
for field,value in (('crc',8),('provider','other'),('kind','EXPORT_SYMBOL_GPL'),('namespace','OTHER_NS')):
    rejected(policy=(replace(POLICY[0],**{field:value}),)+POLICY[1:])
for pinset in ({},dict(pins(),extra='0'*64),dict(pins(),elf='0'*64),dict(pins(),policy='x'*64)):
    rejected(expected_hashes=pinset)
rejected(DATA+b'\0',expected_hashes=pins())  # Cosmetic/trailing change still breaks a supplied content pin.
rejected(table=SYMVERS.replace(b'0x00000001',b'0x00000004'))
rejected(table=SYMVERS+SYMVERS.splitlines(keepends=True)[0])
rejected(table=SYMVERS.replace(b'\tEXPORT_SYMBOL\t',b'\tUNKNOWN\t',1))
rejected(table=SYMVERS.replace(b'\tvmlinux\t',b'\tother\t',1))
ambiguous=SYMVERS.replace(b'\tvmlinux\t',b'\tdrivers/other/fixture-scm\t',1)
rejected(table=ambiguous,policy=(replace(POLICY[0],provider='drivers/other/fixture-scm'),)+POLICY[1:])
rejected(table=SYMVERS.replace(b'FIXTURE_NS',b'OTHER_NS'))
rejected(table=SYMVERS.replace(b'0x00000001',b'0x1'))
rejected(table=b'\xff');rejected(table=b'x'*(v.MAX_SYMVERS_BYTES+1))
for info in (b'license=Proprietary\0depends=fixture-scm\0import_ns=FIXTURE_NS\0',
             b'license=GPL\0depends=\0import_ns=FIXTURE_NS\0',
             b'license=GPL\0depends=fixture-scm,extra\0import_ns=FIXTURE_NS\0',
             b'license=GPL\0depends=fixture-scm\0',INFO+b'import_ns=FIXTURE_NS\0',
             INFO+b'license=GPL\0',INFO[:-1],b'x'*(v.MAX_MODINFO_BYTES+1)+b'\0'):
    rejected(fixture(info=info))
rejected(fixture(duplicate_metadata=True))
rejected(fixture(versions=(*IMPORTS,('module_layout',3),('fixture_api',1))))
rejected(fixture(versions=IMPORTS))
rejected(fixture(undefined=IMPORTS+IMPORTS[:1]))
rejected(fixture(undefined=IMPORTS[:-1]))
rejected(fixture(raw_versions=b'x'))
rejected(fixture(versions=(('fixture_api',1<<32),('fixture_scm',2),('module_layout',3))))
rejected(fixture(raw_versions=struct.pack('<Q',1)+b'x'*56))
rejected(fixture(versions=(('fixture_api',1),)*(v.MAX_IMPORTS+1)))
rejected(policy=(POLICY[0],)*(v.MAX_IMPORTS+1))

# Matching replacement of all caller-supplied bytes/pins is still NOT provenance
# or authorization, even when every local metadata check is PASS.
forged=fixture(versions=(('fixture_api',4),('fixture_scm',2),('module_layout',3)))
forged_table=SYMVERS.replace(b'0x00000001',b'0x00000004')
forged_policy=(replace(POLICY[0],crc=4),)+POLICY[1:]
coherent=review(forged,forged_table,forged_policy,expected_hashes=pins(forged,forged_table,forged_policy))
assert coherent['metadata_consistent'] and coherent['overall']=='PENDING'
rejected(forged,forged_table,forged_policy,expected_hashes=pins())

# Independently archived historical audit is a reference catalog, NOT a default
# policy inferred from the ELF, and NOT approval for a new helper module.
root=here.parents[1]
prior=root/'private-diagnostics/cache-leaf-parser-caller-review-01'
record=json.loads((prior/'artifact-manifest.json').read_text())['files']['historical-interface-audit.json']
audit_bytes=(prior/'historical-interface-audit.json').read_bytes()
assert hashlib.sha256(audit_bytes).hexdigest()==record['sha256']
audit=json.loads(audit_bytes)
HISTORICAL_POLICY=tuple(v.ImportRule(x['symbol'],int(x['elf_crc'],16),x['provider'],x['kind'],x['namespace']) for x in audit['interfaces'])
HISTORICAL=(root/'quest3/module/quest_kexec.ko').read_bytes()
STOCK=(root/'.work/cma-identity-stock-out/Module.symvers').read_bytes()
historical_pins=dict(elf=audit['artifact_sha256'],symvers=audit['symvers_sha256'],policy=v.policy_sha256(HISTORICAL_POLICY))
HISTORICAL_RESULT=v.review(HISTORICAL,STOCK,HISTORICAL_POLICY,expected_hashes=historical_pins)
assert HISTORICAL_RESULT['metadata_consistent'] and HISTORICAL_RESULT['overall']=='PENDING'
assert HISTORICAL_RESULT['observations']['versions']==72 and HISTORICAL_RESULT['observations']['undefined']==71
assert HISTORICAL_RESULT['observations']['dependencies']==['qcom-scm']
assert not HISTORICAL_RESULT['leaf_contract_evaluated'] and not HISTORICAL_RESULT['helper_approved']
assert leaf.inspect_bytes(HISTORICAL)['checks']['L08']['status']=='REJECT'  # No bypass of separate leaf verdict.
print('PASS HOST import consistency: exact version/undefined sets, CRC/provider/kind/namespace/dependency/license, explicit policy and content substitution negatives; coherent bundles never establish build/CFI/lifetime or approval')
