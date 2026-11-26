#!/usr/bin/env python3
"""Model stack/register saves from real disassembly; does NOT emulate MMU/EL1."""
from pathlib import Path
import re, subprocess, random, os
r=Path(__file__).resolve().parents[1]
objdump=Path(os.environ.get('Q3_OBJDUMP', str(r/'clang-prebuilts/clang-r450784e/bin/llvm-objdump')))
def check(path,seed):
    dump=subprocess.check_output([str(objdump),'-d','--no-show-raw-insn',str(path)],text=True)
    body=dump.split('<qkx_roundtrip>:',1)[1].split('\n\n',1)[0]
    rng=random.Random(seed); original={f'x{i}':rng.getrandbits(64) for i in range(31)}
    regs=original.copy(); stack={}; initial_sp=0x100000; sp=initial_sp; jumped=False
    for line in body.splitlines():
        m=re.match(r'\s*[0-9a-f]+:\s+(\w+)\s*(.*)',line)
        if not m: continue
        op,args=m.groups()
        if op=='br':
            assert args=='x1' and not jumped and sp%16==0
            jumped=True
            for i in list(range(18,29))+[30]: regs[f'x{i}']=rng.getrandbits(64)
        elif op in ('stp','ldp','str','ldr'):
            pat=r'(x\d+)(?:, (x\d+))?, \[sp(?:, #(-?(?:0x[0-9a-f]+|\d+)))?\](!)?(?:, #(-?(?:0x[0-9a-f]+|\d+)))?'
            a=re.fullmatch(pat,args); assert a,(op,args)
            first,second,offset,pre,post=a.groups()
            offset=int(offset,16 if '0x' in offset else 10) if offset else 0
            address=sp+offset
            if pre: sp=address
            for i,reg in enumerate([first]+([second] if second else [])):
                addr=address+8*i
                assert initial_sp-96<=addr<initial_sp,addr
                if op.startswith('st'): stack[addr]=regs[reg]
                else: regs[reg]=stack[addr]
            if post: sp+=int(post,16 if '0x' in post else 10)
            assert sp%16==0
        elif op=='ret':
            assert jumped and sp==initial_sp
            return [reg for reg in ['x18']+[f'x{i}' for i in range(19,29)]+['x30'] if regs[reg]!=original[reg]]
        elif op=='bti':
            # Newer disassemblers name the branch-target hint explicitly.
            assert args in ('', 'c', 'j', 'jc'),args
        else:
            assert op in ('hint','mrs','msr','adr','orr','and','mov','isb','dsb','tlbi'),op
            assert 'sp' not in args.lower(),args
    raise AssertionError('Missing return')
for seed in range(100):
    assert check(r/'inputs/quest-kexec/module/quest_kexec.ko',seed)==['x18']
    assert check(r/'module/quest_kexec.ko',seed)==[]
print('PASS: 100 register patterns; original binary loses x18, corrected binary restores x18/x19–x28/LR/SP; frame stays 96-byte/16-byte aligned')
print('Scope: stack/register model on disassembly; privileged instructions/MMU and actual return branch are not executed.')
