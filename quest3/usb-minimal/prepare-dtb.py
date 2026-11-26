#!/usr/bin/env python3
"""Offline target DT transformation. Never writes a live DT or boot partition."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
from fdtcheck import read,rewrite
P='/soc/ssusb@a600000';C=P+'/dwc3@a600000';U='/soc/qcom,pmic_glink/qcom,ucsi'
EP=P+'/port/endpoint';UP=U+'/connector/port/endpoint'
CHANGES={(P,'usb-role-switch'):None,(C,'usb-role-switch'):None,
         (C,'dr_mode'):b'peripheral\0',(C,'maximum-speed'):b'high-speed\0',
         (EP,'remote-endpoint'):None,(UP,'remote-endpoint'):None,(U,'status'):b'disabled\0'}
def check_input(nodes):
    if b'qcom,anorak' not in nodes['/'].get('compatible',b'').split(b'\0') or b'oculus,eureka' not in nodes['/'].get('compatible',b'').split(b'\0'):
        raise ValueError('only the validated Quest 3 Eureka/Anorak layout is supported')
    for path,compat in [(P,b'qcom,dwc-usb3-msm'),(C,b'snps,dwc3'),(U,b'qcom,ucsi-glink')]:
        if compat not in nodes.get(path,{}).get('compatible',b'').split(b'\0'):raise ValueError('unexpected node '+path)
    for path in [EP,UP]:
        if path not in nodes:raise ValueError('missing endpoint '+path)
    for path in [P,C]:
        if any(x in nodes[path] for x in ['extcon','qcom,default-mode-host','qcom,default-mode-none','io-channel-names']):
            raise ValueError('unexpected external role/charger policy at '+path)
    for path in [P,C]:
        if nodes[path].get('status') not in (None,b'okay\0',b'ok\0'):
            raise ValueError('USB node unavailable '+path)
    if nodes[C].get('dr_mode') not in (b'otg\0',b'peripheral\0'):
        raise ValueError('unexpected original USB role')
    if nodes[C].get('maximum-speed') not in (b'super-speed\0',b'high-speed\0'):
        raise ValueError('unexpected original USB maximum speed')
    forward=nodes[EP].get('remote-endpoint');reverse=nodes[UP].get('remote-endpoint')
    if (forward is None)!=(reverse is None):raise ValueError('half-connected endpoint graph')
    if forward is not None and (forward!=nodes[UP].get('phandle') or reverse!=nodes[EP].get('phandle')):
        raise ValueError('unexpected connector graph')
    phys=nodes[C].get('usb-phy',b'')
    if len(phys)!=8:raise ValueError('MSM glue requires both legacy PHY phandles')
    if b'usb3gen2en' in nodes.get('/chosen',{}).get('bootargs',b''):
        raise ValueError('bootargs override the USB speed')
    providers={v.get('phandle'):v for v in nodes.values() if 'phandle' in v}
    for ref,compat in [(phys[:4],b'qcom,usb-hsphy-snps-femto'),(phys[4:],b'qcom,usb-ssphy-qmp-dp-combo')]:
        provider=providers.get(ref,{})
        if compat not in provider.get('compatible',b'').split(b'\0') or provider.get('status') not in (None,b'okay\0',b'ok\0'):
            raise ValueError('unexpected or disabled PHY provider')

def verify(before,after):
    a,res,cpu=read(before);b,res2,cpu2=read(after)
    check_input(a)
    if res!=res2 or cpu!=cpu2 or set(a)!=set(b):raise ValueError('nodes/reservations/boot CPU changed')
    changes=[]
    for path in a:
        for name in a[path].keys()|b[path].keys():
            old=a[path].get(name);new=b[path].get(name)
            if old!=new:
                if (path,name) not in CHANGES or new!=CHANGES[path,name]:raise ValueError('unexpected change '+path+':'+name)
                changes.append({'path':path,'property':name})
    for (path,name),value in CHANGES.items():
        if b[path].get(name)!=value:raise ValueError('missing target setting '+name)
    return changes
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--dtc');args=p.parse_args()
    original=args.input.read_bytes();nodes,res,cpu=read(original);check_input(nodes)
    if args.out.exists() or args.input.resolve()==args.out.resolve():p.error('output must be a new file')
    result=rewrite(original,CHANGES);changes=verify(original,result)
    if args.dtc:
        with tempfile.TemporaryDirectory() as work:
            test=Path(work)/'target.dtb';test.write_bytes(result)
            # Binary-to-binary validation avoids the old dtc string escape bug.
            check=subprocess.run([args.dtc,'-I','dtb','-O','dtb','-b',str(cpu),str(test)],capture_output=True,check=True)
            verify(original,check.stdout)
            warnings=check.stderr
    else:
        warnings=b'Independent dtc validation not requested.\n'
    with args.out.open('xb') as f:f.write(result)
    args.out.with_suffix(args.out.suffix+'.dtc-warnings.txt').write_bytes(warnings)
    report={'input_sha256':hashlib.sha256(original).hexdigest(),'output_sha256':hashlib.sha256(result).hexdigest(),'allowed_changes':changes,'all_other_properties_unchanged':True,'both_PHY_references_preserved':True,'memory_reservations_preserved':True,'boot_tested':False}
    args.out.with_suffix(args.out.suffix+'.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
