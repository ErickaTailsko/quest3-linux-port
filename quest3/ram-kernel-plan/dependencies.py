from pathlib import Path
import re,json,fnmatch
root=Path(__file__).resolve().parents[1]
lines=(root/'device-review/quest3-live.dts').read_text().splitlines()
nodes={}; stack=[]
for l in lines:
 s=l.strip()
 if s.endswith('{'):
  name=s[:-1].strip();path=('/'+'/'.join(stack+[name])).replace('//','/').replace('//','/')
  stack.append(name);nodes[path]={'path':path,'props':{}}
 elif s.startswith('};'):
  stack.pop()
 elif stack and '=' in s and s.endswith(';'):
  name,value=s[:-1].split('=',1);nodes[('/'+'/'.join(stack)).replace('//','/').replace('//','/')]['props'][name.strip()]=value.strip()
ph={}
for node in nodes.values():
 p=node['props'].get('phandle','')
 if p:ph[int(re.search(r'0x[0-9a-f]+|\d+',p)[0],0)]=node
aliases=[];modules={}
for f in (root/'native-kexec-probe').rglob('*.ko'):
 b=f.read_bytes();name=f.stem.replace('-','_');modules[name]=f
 for a in re.findall(rb'\x00alias=([^\x00]+)',b):
  aliases.append((a.decode(errors='replace'),name))
props={'clocks':'#clock-cells','resets':'#reset-cells','interconnects':'#interconnect-cells','iommus':'#iommu-cells','power-domains':'#power-domain-cells','interrupts-extended':'#interrupt-cells'}
queue=[n for n in nodes.values() if '/ssusb@a600000' in n['path']]
seen={};external=[]
while queue:
 node=queue.pop();path=node['path']
 if path in seen:continue
 p=node['props']; comp=[c for part in re.findall(r'"([^"]+)"',p.get('compatible','')) for c in part.split(r'\0')]
 matches=sorted({name for a,name in aliases for c in comp if fnmatch.fnmatchcase('of:N*T*C'+c,a)})
 seen[path]={'compatible':comp,'modules':matches}
 # Include owning controller for referenced subnodes.
 parent=path.rsplit('/',1)[0]
 if parent in nodes and parent!='/':queue.append(nodes[parent])
 for key,value in p.items():
  if not (key in props or key.endswith('-supply') or key in ['usb-phy','pinctrl-0','extcon','remote-endpoint']):continue
  vals=[int(x,0) for x in re.findall(r'0x[0-9a-fA-F]+|\b\d+\b',value)]
  i=0
  while i<len(vals):
   ref=ph.get(vals[i]);i+=1
   if ref is None:external.append([path,key,'unknown phandle']);break
   queue.append(ref)
   cell=props.get(key)
   if cell:
    raw=ref['props'].get(cell)
    if raw is None:external.append([path,key,'missing '+cell]);break
    i+=int(re.search(r'0x[0-9a-f]+|\d+',raw)[0],0)
needed={m for x in seen.values() for m in x['modules']}
needed.update({'rpmh_regulator','gcc_anorak','gdsc_regulator','ucsi_glink'})
start=set(needed)
while True:
 add=set()
 for name in needed:
  b=modules[name].read_bytes();m=re.search(rb'\x00depends=([^\x00]*)',b)
  if m:add.update(x.replace('-','_') for x in m[1].decode().split(',') if x)
 if add<=needed:break
 assert add<=modules.keys(),add-modules.keys()
 needed.update(add)
result={'dt_providers':seen,'dt_module_roots':sorted(start),'all_module_dependencies':sorted(needed),'unresolved_references':external}
Path(__file__).with_name('dependencies.json').write_text(json.dumps(result,indent=2)+'\n')
print('DT provider modules:',sorted(start));print('Transitive modules:',sorted(needed));print('Unresolved references:',external)
