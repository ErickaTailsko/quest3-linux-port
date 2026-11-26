"""Run init control flow with a simulated filesystem and stubbed system calls.
No mounts, listeners, interfaces or device writes are performed.
"""
from pathlib import Path
import tempfile,subprocess,re
r=Path(__file__).parent
for case in ['ready','wrong-role','wrong-speed','wrong-udc','missing-udc','multiple-udc','role-switch','bind-failure']:
 with tempfile.TemporaryDirectory() as work:
  base=Path(work);dt=base/'sys/firmware/devicetree/base/soc/ssusb@a600000';core=dt/'dwc3@a600000';core.mkdir(parents=True)
  (core/'dr_mode').write_bytes(b'host\0' if case=='wrong-role' else b'peripheral\0')
  (core/'maximum-speed').write_bytes(b'super-speed\0' if case=='wrong-speed' else b'high-speed\0')
  if case=='role-switch':(dt/'usb-role-switch').touch()
  udcs=base/'sys/class/udc';udcs.mkdir(parents=True)
  if case!='missing-udc':
   name='wrong.dwc3' if case=='wrong-udc' else 'a600000.dwc3'
   (udcs/name).mkdir();(udcs/name/'maximum_speed').write_text('high-speed\n')
  if case=='multiple-udc':(udcs/'other.dwc3').mkdir()
  (base/'dev').mkdir();(base/'dev/console').touch();(base/'dev/kmsg').touch()
  src=(r/'init').read_text().replace('/bin/busybox --install -s /bin',': # installer simulated')
  src=src.replace('fail() { echo "q3-ram: FAILED: $*" >/dev/console; while :; do sleep 60; done; }','fail() { echo "FAILED: $*" >/dev/console; exit 17; }')
  src=re.sub(r'/(sys|dev|config|tmp)(?=[/"\s])',lambda m:str(base/m[1]),src)
  prefix=f'''#!/bin/sh
mount() {{ printf '%s\\n' "$*" >> '{base}/mounts'; }}
ifconfig() {{ printf '%s\\n' "$*" >> '{base}/ifconfig'; }}
telnetd() {{ :; }}
sleep() {{ :; }}
kill() {{ return 1; }}
dmesg() {{ echo simulated-dmesg; }}
'''
  if case=='bind-failure':
   # Make redirection to UDC fail after creating the function link.
   prefix+=f'''ln() {{ command ln "$@"; command mkdir -p '{base}/config/usb_gadget/q3ram/UDC'; }}\n'''
  script=base/'init-test.sh';script.write_text(prefix+src)
  result=subprocess.run(['/bin/sh',str(script)],capture_output=True,text=True,timeout=5)
  console=(base/'dev/console').read_text();log=(base/'dev/kmsg').read_text()
  if case=='ready':
   assert 'ECM ready' in log and 'telnetd-exited' in console
   assert (base/'config/usb_gadget/q3ram/UDC').read_text().strip()=='a600000.dwc3'
   assert 'usb0 10.42.0.2' in (base/'ifconfig').read_text()
   assert (base/'config/usb_gadget/q3ram/max_speed').read_text().strip()=='high-speed'
   assert not any('/dev/block' in l for l in (base/'mounts').read_text().splitlines())
  else:
   assert 'ECM ready' not in log and not (base/'ifconfig').exists(),case
  assert result.returncode==17,(case,result.returncode,console)
print('PASS: init flow under simulated filesystem; ECM setup, fixed DT checks, wrong/missing/multiple UDC, role-switch refusal, bind failure before network setup; no real mounts/network/hardware')
