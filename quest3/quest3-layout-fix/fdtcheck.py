"""Small strict read-only FDT reader for semantic before/after comparison."""
import struct

def read(blob):
    if len(blob)<40: raise ValueError('truncated header')
    magic,total,offstruct,offstrings,offreserve,version,last,cpu,stringsize,structsize=struct.unpack_from('>10I',blob)
    if magic!=0xd00dfeed or total>len(blob) or version!=17 or last>17:
        raise ValueError('unsupported FDT header')
    for off,size in [(offstruct,structsize),(offstrings,stringsize)]:
        if off<40 or off+size>total: raise ValueError('invalid block')
    strings=blob[offstrings:offstrings+stringsize]
    reserved=[];at=offreserve
    while True:
        if at+16>total:raise ValueError('truncated reservations')
        address,size=struct.unpack_from('>QQ',blob,at);at+=16
        if address==size==0:break
        reserved.append((address,size))
    nodes={};stack=[];pos=offstruct;end=pos+structsize
    def string(data,start):
        finish=data.find(b'\0',start)
        if finish<0:raise ValueError('unterminated string')
        return data[start:finish].decode(),finish+1
    while pos+4<=end:
        token=struct.unpack_from('>I',blob,pos)[0];pos+=4
        if token==1:
            name,nextpos=string(blob,pos)
            if nextpos>end:raise ValueError('node exceeds structure')
            if '/' in name or (not stack and name):raise ValueError('invalid node name')
            stack.append(name);pos=(nextpos+3)&~3
            path='/'+'/'.join(stack[1:])
            if path in nodes:raise ValueError('duplicate node')
            nodes[path]={}
        elif token==2:
            if not stack:raise ValueError('unbalanced nodes')
            stack.pop()
        elif token==3:
            if not stack or pos+8>end:raise ValueError('invalid property')
            size,nameoff=struct.unpack_from('>II',blob,pos);pos+=8
            if nameoff>=len(strings) or pos+size>end:raise ValueError('invalid property bounds')
            name,_=string(strings,nameoff);props=nodes['/'+'/'.join(stack[1:])]
            if name in props:raise ValueError('duplicate property')
            props[name]=blob[pos:pos+size];pos=(pos+size+3)&~3
        elif token==4:pass
        elif token==9:
            if stack or '/' not in nodes:raise ValueError('unbalanced FDT')
            return nodes,reserved,cpu
        else:raise ValueError('unknown structure token')
    raise ValueError('no FDT_END')

def rewrite(blob, changes):
    """Edit only named properties, preserving all other token bytes and data."""
    nodes,reserved,cpu=read(blob)
    header=struct.unpack_from('>10I',blob)
    _,_,offstruct,offstrings,offreserve,version,last,_,stringsize,structsize=header
    strings=bytearray(blob[offstrings:offstrings+stringsize]);offsets={}
    at=0
    while at<len(strings):
        finish=strings.index(0,at);offsets[bytes(strings[at:finish]).decode()]=at;at=finish+1
    def prop(name,value):
        if name not in offsets:
            offsets[name]=len(strings);strings.extend(name.encode()+b'\0')
        record=struct.pack('>III',3,len(value),offsets[name])+value
        return record+b'\0'*(-len(record)%4)
    output=bytearray();stack=[];pos=offstruct;end=offstruct+structsize
    while pos+4<=end:
        start=pos;token=struct.unpack_from('>I',blob,pos)[0];pos+=4
        if token==1:
            finish=blob.index(0,pos);name=blob[pos:finish].decode();pos=(finish+4)&~3
            stack.append(name);path='/'+'/'.join(stack[1:]);output.extend(blob[start:pos])
            for (target,name),value in changes.items():
                if target==path and value is not None and name not in nodes[path]:
                    output.extend(prop(name,value))
        elif token==2:
            stack.pop();output.extend(blob[start:pos])
        elif token==3:
            size,nameoff=struct.unpack_from('>II',blob,pos);pos+=8
            finish=strings.index(0,nameoff);name=bytes(strings[nameoff:finish]).decode()
            pos=(pos+size+3)&~3;key=('/'+'/'.join(stack[1:]),name)
            if key not in changes:output.extend(blob[start:pos])
            elif changes[key] is not None:output.extend(prop(name,changes[key]))
        elif token==4:output.extend(blob[start:pos])
        elif token==9:
            output.extend(blob[start:pos]);break
    reservations=b''.join(struct.pack('>QQ',a,n) for a,n in reserved)+bytes(16)
    newstruct=40+len(reservations);newstrings=newstruct+len(output)
    total=newstrings+len(strings)
    return struct.pack('>10I',0xd00dfeed,total,newstruct,newstrings,40,version,last,cpu,len(strings),len(output))+reservations+output+strings
