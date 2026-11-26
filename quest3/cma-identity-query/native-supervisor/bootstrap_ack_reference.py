#!/usr/bin/env python3
"""One-shot HOST FIXTURE journal for bootstrap ACK/pin-import boundaries.

No native activation, production transport completion, controller integration or
writer recovery API. Caller-supplied fixtures do not authenticate a remote peer.
An existing journal (including incomplete state) is never opened for writing.
"""
import fcntl
import hashlib
import os
from pathlib import Path

import bootstrap_receipt as b

NAME = 'q3-bootstrap-pin-ack'
PROFILE = 'q3-bootstrap-pin-ack-host-reference-v1'
LIMIT = 16384


class Frozen(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def flags():
    return dict(execution_enabled=False, admission_enabled=False, pin_import_permitted=False,
                local_pin_ack_verified=False, bootstrap_verified=False, authorization_verified=False,
                original_response_verified=False, publication_durability_verified=False,
                replay_permitted=False, cleanup_permitted=False, automatic_resume_allowed=False,
                safe_to_mutate=False, controller_integrated=False)


def _identity(info):
    return (info.st_dev, info.st_ino)


def _pins(values, count):
    if (not isinstance(values, (list, tuple)) or len(values)!=count or
            any(type(v) is not int or not 0 <= v < 1 << 64 for v in values) or
            any(not values[i] for i in range(1,count,2))):
        raise ValueError('explicit prior pins required')
    return tuple(values)


def _catalog(fd, maximum=8):
    result=set()
    with os.scandir(fd) as entries:
        for entry in entries:
            result.add(entry.name)
            if len(result)>maximum: raise ValueError('oversized local catalogue')
    return result


def _read(fd, name):
    before=os.stat(name,dir_fd=fd,follow_symlinks=False); b._private(before)
    if before.st_size>=LIMIT: raise ValueError('oversized local record')
    opened=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=fd)
    try:
        if b._stamp(os.fstat(opened))!=b._stamp(before): raise ValueError('local record replaced')
        data=b''
        while len(data)<LIMIT:
            chunk=os.read(opened,LIMIT-len(data))
            if not chunk: break
            data+=chunk
        if (len(data)>=LIMIT or b._stamp(os.fstat(opened))!=b._stamp(before) or
                b._stamp(os.stat(name,dir_fd=fd,follow_symlinks=False))!=b._stamp(before)):
            raise ValueError('local record changed')
        return data
    finally:
        os.close(opened)


def _intent(request, parent, root, lease):
    b.parse_request(request)
    return b.canonical(dict(schema=1,profile=PROFILE,producer='host-fixture-journal',
                            request=b.parse_request(request),request_sha256=b.request_commitment(request),
                            local_parent_pins=list(parent),local_root_pins=list(root),
                            local_lease_pins=list(lease),**flags()))


class HostAckJournal:
    """Single-threaded host-only writer; no reopen/reset/takeover/resume.

    Only a caller-held checkpoint returned after successful local fsync may be
    used by import_fixture_pins in this same live writer. Disk reads never issue
    that capability. No method here calls a peer or invokes a controller.
    """

    @classmethod
    def create(cls, parent_path, parent_pins, request, *, fault=None):
        b.parse_request(request)
        self=cls.__new__(cls)
        self.parent_path=Path(parent_path)
        self.parent_pins=_pins(parent_pins,2)
        self.request=request
        self.parent=self.root=self.lease=None
        self.poisoned=False
        self.fault=fault  # injected HOST test hook; never a transport callback
        self.expected={'lease.lock'}
        self.checkpoint=None
        self.imported=False
        try:
            info=self.parent_path.lstat(); b._private(info,True)
            if _identity(info)!=self.parent_pins: raise ValueError('local parent replaced')
            self.parent=os.open(self.parent_path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            if b._stamp(os.fstat(self.parent))!=b._stamp(info): raise ValueError('local parent changed')
            os.mkdir(NAME,0o700,dir_fd=self.parent)  # existing state is terminal
            self.root=os.open(NAME,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.parent)
            root_info=os.fstat(self.root); b._private(root_info,True)
            self.root_pins=_identity(root_info)
            self.lease=os.open('lease.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root)
            lease_info=os.fstat(self.lease); b._private(lease_info)
            self.lease_pins=_identity(lease_info)
            fcntl.flock(self.lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self._check()
            os.fsync(self.lease); os.fsync(self.root); os.fsync(self.parent)
            self.intent=_intent(request,self.parent_pins,self.root_pins,self.lease_pins)
            self._publish('intent',self.intent)
            return self
        except BaseException:
            self.poisoned=True
            self.close()
            raise

    def close(self):
        for name in ('lease','root','parent'):
            fd=getattr(self,name,None)
            if fd is not None:
                os.close(fd); setattr(self,name,None)

    def _point(self, name):
        if self.fault is not None: self.fault(name)

    def _check(self):
        if self.poisoned or self.root is None: raise Frozen('closed/frozen local journal')
        for opened,path_info,pins,directory in (
                (self.parent,self.parent_path.lstat(),self.parent_pins,True),
                (self.root,os.stat(NAME,dir_fd=self.parent,follow_symlinks=False),self.root_pins,True),
                (self.lease,os.stat('lease.lock',dir_fd=self.root,follow_symlinks=False),self.lease_pins,False)):
            fd_info=os.fstat(opened); b._private(fd_info,directory); b._private(path_info,directory)
            if _identity(fd_info)!=pins or _identity(path_info)!=pins:
                raise Frozen('local journal identity changed')
        if _catalog(self.root)!=self.expected: raise Frozen('incomplete/foreign local journal')

    def _publish(self, name, data):
        if not isinstance(data,bytes) or not 0<len(data)<LIMIT: raise ValueError('bounded record required')
        self._check()
        pending=name+'.pending'; final=name+'.json'
        fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root)
        try:
            position=0
            while position<len(data):
                written=os.write(fd,data[position:])
                if written<=0: raise OSError('short journal write')
                position+=written
            self._point(name+'-file-fsync'); os.fsync(fd)
        finally:
            os.close(fd)
        self._point(name+'-link')
        os.link(pending,final,src_dir_fd=self.root,dst_dir_fd=self.root,follow_symlinks=False)
        self._point(name+'-directory-fsync'); os.fsync(self.root)
        self._point(name+'-unlink'); os.unlink(pending,dir_fd=self.root)
        self._point(name+'-final-fsync'); os.fsync(self.root)
        self.expected.add(final)
        self._check()
        if _read(self.root,final)!=data: raise Frozen('published journal bytes changed')

    def acknowledge_fixture(self, receipt, response, observed_pins, *, completion):
        """Commit supplied HOST FIXTURE evidence, not real transport completion.

        The completion literal cannot authenticate execution. Production needs a
        reviewed transport/context protocol; matching reply bytes are insufficient.
        """
        try:
            self._check()
            if (self.checkpoint is not None or type(completion) is not str or
                    completion!='host-fixture-complete'):
                raise Frozen('repeated ACK or unknown fixture completion')
            parsed=b.parse_receipt(receipt,self.request)
            if _pins(observed_pins,4)!=tuple(parsed['candidate_pins']):
                raise ValueError('independently supplied fixture pins mismatch')
            b.reply_matches(response,self.request,parsed['receipt_sha256'])
            if _read(self.root,'intent.json')!=self.intent: raise Frozen('local intent changed')
            ack=b.canonical(dict(schema=1,profile=PROFILE,producer='host-fixture-journal',
                intent_sha256=digest(self.intent),request_sha256=b.request_commitment(self.request),
                receipt_sha256=parsed['receipt_sha256'],receipt=b._parse(receipt,4096),
                response_ascii=response.decode('ascii'),candidate_pins=parsed['candidate_pins'],
                completion='host-fixture-complete',**flags()))
            self._publish('ack',ack)
            self._point('ack-before-return')
            self._check()
            if _read(self.root,'intent.json')!=self.intent or _read(self.root,'ack.json')!=ack:
                raise Frozen('local evidence changed before ACK return')
            # This in-memory capability is NOT reconstructed by observe().
            self.checkpoint=(digest(self.intent),digest(ack),*self.root_pins,*self.lease_pins)
            self.ack=ack
            return self.checkpoint
        except BaseException:
            self.poisoned=True
            raise

    def import_fixture_pins(self, checkpoint):
        """Separate explicit host-fixture import; still no admission/activation."""
        try:
            self._check()
            if (self.imported or self.checkpoint is None or type(checkpoint) is not tuple or
                    checkpoint!=self.checkpoint):
                raise Frozen('caller-held live ACK checkpoint required')
            if _read(self.root,'intent.json')!=self.intent or _read(self.root,'ack.json')!=self.ack:
                raise Frozen('local ACK/intent changed')
            ack=b._parse(self.ack,LIMIT)
            record=b.canonical(dict(schema=1,profile=PROFILE,producer='host-fixture-journal',
                intent_sha256=digest(self.intent),ack_sha256=digest(self.ack),
                imported_fixture_pins=ack['candidate_pins'],**flags()))
            self._publish('import',record)
            self._point('import-before-return')
            self._check()
            if (_read(self.root,'intent.json')!=self.intent or _read(self.root,'ack.json')!=self.ack or
                    _read(self.root,'import.json')!=record):
                raise Frozen('local evidence changed before import return')
            self.imported=True
            return dict(state='fixture-pins-imported-no-activation',
                        imported_fixture_pins=ack['candidate_pins'],import_sha256=digest(record),**flags())
        except BaseException:
            self.poisoned=True
            raise


def observe(parent_path, parent_pins, journal_pins, request):
    """Read-only forensic snapshot under caller-held pins, never recovers a writer.

    Complete bytes may survive an unconfirmed fsync/return. No checkpoint is
    returned, and no completed-durability/import permission is inferred.
    """
    result=dict(state='unknown',complete_records=0,**flags())
    parent=root=lease=None
    try:
        parent_pins=_pins(parent_pins,2); journal_pins=_pins(journal_pins,4)
        parent_path=Path(parent_path)
        before=parent_path.lstat(); b._private(before,True)
        if _identity(before)!=parent_pins: raise ValueError('prior local parent anchor mismatch')
        parent=os.open(parent_path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        root=os.open(NAME,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
        lease=os.open('lease.lock',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=root)
        snapshots=[os.fstat(fd) for fd in (parent,root,lease)]
        for info,directory in zip(snapshots,(True,True,False)): b._private(info,directory)
        if (b._stamp(snapshots[0])!=b._stamp(before) or
                _identity(snapshots[1])+_identity(snapshots[2])!=journal_pins):
            raise ValueError('local journal pins mismatch')
        try: fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            result['state']='lease-held'; return result
        names=_catalog(root)
        allowed={'lease.lock','intent.json','ack.json','import.json'}
        if names-allowed or 'intent.json' not in names or 'import.json' in names and 'ack.json' not in names:
            raise ValueError('incomplete/foreign local records')
        intent=_read(root,'intent.json')
        if intent!=_intent(request,parent_pins,journal_pins[:2],journal_pins[2:]):
            raise ValueError('local intent/context mismatch')
        records={'intent.json':intent}
        if 'ack.json' in names:
            raw=_read(root,'ack.json'); ack=b._parse(raw,LIMIT)
            receipt=b.canonical(ack['receipt']); parsed=b.parse_receipt(receipt,request)
            response=ack['response_ascii'].encode('ascii'); b.reply_matches(response,request,parsed['receipt_sha256'])
            expected=dict(schema=1,profile=PROFILE,producer='host-fixture-journal',
                intent_sha256=digest(intent),request_sha256=b.request_commitment(request),
                receipt_sha256=parsed['receipt_sha256'],receipt=b._parse(receipt,4096),
                response_ascii=response.decode('ascii'),candidate_pins=parsed['candidate_pins'],
                completion='host-fixture-complete',**flags())
            if b.canonical(expected)!=raw: raise ValueError('local ACK context/fields mismatch')
            records['ack.json']=raw
        if 'import.json' in names:
            raw=_read(root,'import.json')
            expected=dict(schema=1,profile=PROFILE,producer='host-fixture-journal',
                intent_sha256=digest(intent),ack_sha256=digest(records['ack.json']),
                imported_fixture_pins=parsed['candidate_pins'],**flags())
            if b.canonical(expected)!=raw: raise ValueError('local import linkage mismatch')
            records['import.json']=raw
        if _catalog(root)!=names: raise ValueError('local catalogue changed')
        current=(parent_path.lstat(),os.stat(NAME,dir_fd=parent,follow_symlinks=False),
                 os.stat('lease.lock',dir_fd=root,follow_symlinks=False))
        for fd,previous,path_info in zip((parent,root,lease),snapshots,current):
            if b._stamp(os.fstat(fd))!=b._stamp(previous) or b._stamp(path_info)!=b._stamp(previous):
                raise ValueError('local objects replaced during observation')
        for name,raw in records.items():
            if _read(root,name)!=raw: raise ValueError('local record changed during observation')
        result.update(state='fixture-records-observed-not-recovered',complete_records=len(records))
        return result
    except Exception as error:
        result['error_kind']=type(error).__name__
        return result
    finally:
        for fd in (lease,root,parent):
            if fd is not None: os.close(fd)
