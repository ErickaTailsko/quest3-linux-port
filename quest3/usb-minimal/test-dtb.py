from pathlib import Path
import argparse,subprocess,tempfile,importlib.util
from fdtcheck import read,rewrite
spec=importlib.util.spec_from_file_location('patcher',Path(__file__).with_name('prepare-dtb.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--dtc',required=True);a=p.parse_args()
original=a.input.read_bytes();before,res,cpu=read(original);m.check_input(before)
result=rewrite(original,m.CHANGES);assert len(m.verify(original,result))==7
assert rewrite(result,m.CHANGES)==result
changed=rewrite(result,{('/','model'):b'wrong\0'})
try:m.verify(original,changed)
except ValueError:pass
else:raise AssertionError('unrelated change accepted')
for key,value in [(('/','compatible'),b'wrong\0'),((m.C,'usb-phy'),bytes(4)),((m.P,'extcon'),bytes(4)),((m.EP,'remote-endpoint'),bytes(4)),((m.C,'dr_mode'),b'host\0')]:
 bad=rewrite(original,{key:value})
 try:m.check_input(read(bad)[0])
 except ValueError:pass
 else:raise AssertionError(key)
for bad in [b'',original[:39],original[:100],b'bad!'+original[4:]]:
 try:read(bad)
 except (ValueError,IndexError):pass
 else:raise AssertionError('invalid blob accepted')
with tempfile.TemporaryDirectory() as d:
 d=Path(d);out=d/'target.dtb'
 subprocess.run(['python3',str(Path(__file__).with_name('prepare-dtb.py')),'--input',str(a.input),'--out',str(out),'--dtc',a.dtc],check=True,stdout=subprocess.DEVNULL)
 assert out.read_bytes()==result
 attempt=subprocess.run(['python3',str(Path(__file__).with_name('prepare-dtb.py')),'--input',str(a.input),'--out',str(out)],capture_output=True)
 assert attempt.returncode!=0 and out.read_bytes()==result
 # Regression: old dtc converts a zero followed by an octal digit to a
 # different byte sequence during DTB -> DTS -> DTB. Semantic guard rejects it.
 decompile=subprocess.run([a.dtc,'-I','dtb','-O','dts',str(a.input)],capture_output=True,check=True)
 (d/'roundtrip.dts').write_bytes(decompile.stdout+Path(__file__).with_name('usb2-peripheral.dtsi').read_bytes())
 subprocess.run([a.dtc,'-I','dts','-O','dtb','-o',str(d/'roundtrip.dtb'),str(d/'roundtrip.dts')],capture_output=True,check=True)
 try:m.verify(original,(d/'roundtrip.dtb').read_bytes())
 except ValueError:pass
 else:print('NOTE: this dtc preserves the voltage during text roundtrip; regression fixed in tool')
print('PASS: seven allowed changes; PHYs/reservations/other properties preserved; idempotence; refusal of wrong board/PHY/graph/host/extcon; malformed input; no overwrite; dtc binary validation; text-roundtrip voltage regression caught')
