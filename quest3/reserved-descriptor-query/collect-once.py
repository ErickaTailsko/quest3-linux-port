#!/usr/bin/env python3
"""One consented fixed-list descriptor query; never retries insertion or acquires pages."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import uuid

EXPECTED = '6ac24447b03474a6343a25fe19871a43b0a9e6f383c2e6301ff7b5803c80d066'
EXPECTED_CONFIG_GZ = 'a8fc09c1b78fb07216b9dfaef2f91a8108780471aa8e157589924ac8042c6260'
EXPECTED_DTB = '7b377234c27f8c4c0d3ba8f48a1502e5aaff5f85ec476d8e90dc4ca22aca5077'
NAME = 'q3_reserved_descriptors'
SYSFS = '/sys/kernel/' + NAME
SPECS = [('linux,cma',32),('user_contig_region',16),('qseecom_region',20),
         ('qseecom_ta_region',16),('cdsp_eva_region',4),('adsp_heap_region',12),
         ('secure_cdsp_region',40),('sp_region',16),('va_md_mem_region',16),
         ('audio_cma_region',16),('non_secure_display_region',164),
         ('cnss_wlan_region',32),('mem_dump_region',12)]


def validate_report(text):
    lines = text.strip().splitlines()
    if not lines or lines[0] != 'descriptors_only=1 count=13 complete=13 owned=0 dma_safe=0 cpu_pause=0' or len(lines) != 14:
        raise ValueError('incomplete or inconsistent descriptor report')
    regions = []
    for (name, mib), line in zip(SPECS, lines[1:]):
        match = re.fullmatch(r'name=([^ ]+) base=0x([0-9a-f]+) size=0x([0-9a-f]+) ops=1 priv=1 error=0', line)
        if not match or match[1] != name:
            raise ValueError('unexpected name or failed descriptor setup')
        base, size = int(match[2],16), int(match[3],16)
        lower, upper = (0x100000000, (1<<64)-1) if name == 'va_md_mem_region' else (0, 0xffffffff)
        if not base or size != mib*1024*1024 or base % (4*1024*1024) or base < lower or base+size > upper:
            raise ValueError('descriptor address, size or alignment differs from reviewed constraints')
        regions.append({'node':'/reserved-memory/'+name, 'base':hex(base),
                        'end_exclusive':hex(base+size), 'size_bytes':size,
                        'ops_present':True,'priv_present':True,'descriptor_consistent':True})
    for index,a in enumerate(regions):
        for b in regions[index+1:]:
            if max(int(a['base'],16),int(b['base'],16)) < min(int(a['end_exclusive'],16),int(b['end_exclusive'],16)):
                raise ValueError('overlapping descriptors')
    return regions


def collect(out, module, serial, adb='adb', runner=subprocess.run):
    if hashlib.sha256(module.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('module differs from reviewed binary; nothing sent')
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    prefix = [adb,'-s',serial]
    remote = '/data/local/tmp/eris-rmem-'+uuid.uuid4().hex+'.ko'
    report = {'status':'incomplete','insertion_attempts':0,'module_sha256':EXPECTED,
              'cpu_pause_requested':False,'page_acquisition_requested':False,
              'reboot_requested':False,'cleanup_confirmed':False,
              'temporary_cleanup_confirmed':False,'events':[]}
    boot = None
    uploaded = False

    def save():
        (out/'operation.json').write_text(json.dumps(report,indent=2)+'\n')

    def read(command):
        event = {'command':command}
        report['events'].append(event)
        save()
        try:
            result = runner(prefix+['exec-out','su -c '+shlex.quote(command)],capture_output=True,timeout=30)
        except (subprocess.TimeoutExpired,OSError) as error:
            event['error'] = type(error).__name__
            save()
            raise
        event.update(returncode=result.returncode,stdout=result.stdout.decode(errors='replace'),
                     stderr=result.stderr.decode(errors='replace'))
        save()
        if result.returncode:
            raise RuntimeError('read/action failed; no retry: '+command)
        return result.stdout

    def absent(path):
        # Some su wrappers lose failure status; require explicit output as well.
        value = read('if test -e '+shlex.quote(path)+'; then echo PRESENT; else echo ABSENT; fi').strip()
        if value != b'ABSENT':
            raise RuntimeError('path already present or absence not confirmed')

    def modules():
        return [line.split()[0] for line in read('cat /proc/modules').splitlines() if line.split()]

    def boot_id():
        value = read('cat /proc/sys/kernel/random/boot_id').strip()
        if not re.fullmatch(rb'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value):
            raise ValueError('invalid boot identity')
        return value

    save()
    try:
        if not read('id').startswith(b'uid=0('):
            raise ValueError('existing root not confirmed')
        if read('uname -r').strip() != b'5.10.246-gd7102a837402':
            raise ValueError('unexpected running kernel')
        boot = boot_id()
        report['boot_id_before'] = boot.decode()
        for path,expected in [('/proc/config.gz',EXPECTED_CONFIG_GZ),('/sys/firmware/fdt',EXPECTED_DTB)]:
            if read('sha256sum '+path).split()[0].decode() != expected:
                raise ValueError('runtime config/DT differs from reviewed capture')
        report['cpus_before'] = read('cat /sys/devices/system/cpu/online').strip().decode()
        if NAME.encode() in modules():
            raise ValueError('module already present; no ownership assumed')
        absent(SYSFS)
        absent(remote)
        uploaded = True  # A lost transfer response may leave our partial file.
        save()
        # Large adb push disconnected this device before insertion. Use the
        # previously reviewed 4KiB offset-write technique, without any retries.
        payload = module.read_bytes()
        report['transfer'] = 'fixed-offset-4096-byte-chunks; no retry'
        read('umask 077; : > '+remote)
        for offset in range(0,len(payload),4096):
            encoded = base64.b64encode(payload[offset:offset+4096]).decode('ascii')
            read('printf %s '+encoded+' | base64 -d | dd of='+remote+
                 ' bs=4096 seek='+str(offset//4096)+' conv=notrunc 2>/dev/null')
        if read('wc -c '+remote).split()[0].decode() != str(len(payload)):
            raise ValueError('remote module byte count differs')
        if read('sha256sum '+remote).split()[0].decode() != EXPECTED:
            raise ValueError('remote module hash differs')
        if boot_id() != boot:
            raise ValueError('boot changed before insertion')
        report['insertion_attempts'] = 1
        save()  # Persist intent before the single uncertain operation.
        read('insmod '+remote+' inspect=1')
        data = read('cat '+SYSFS+'/report')
        with (out/'descriptors.txt').open('xb') as stream:
            stream.write(data)
        report['regions'] = validate_report(data.decode('ascii'))
        report['report_sha256'] = hashlib.sha256(data).hexdigest()
        if boot_id() != boot:
            raise ValueError('boot changed during query')
        report['status'] = 'descriptors-verified'
    except Exception as error:
        report['error'] = repr(error)
    finally:
        try:
            if boot is None:
                raise RuntimeError('no confirmed boot; no unowned cleanup')
            current = boot_id()
            report['boot_id_after'] = current.decode()
            if current != boot:
                raise RuntimeError('boot changed; no unowned cleanup in a new boot')
            if report['insertion_attempts'] and NAME.encode() in modules():
                read('rmmod '+NAME)
            if NAME.encode() in modules():
                raise RuntimeError('module remains present')
            absent(SYSFS)
            report['cleanup_confirmed'] = True
            if uploaded:
                read('rm -f '+remote)
                absent(remote)
            report['temporary_cleanup_confirmed'] = True
            report['cpus_after'] = read('cat /sys/devices/system/cpu/online').strip().decode()
            if 'cpus_before' in report and report['cpus_before'] != report['cpus_after']:
                raise RuntimeError('online CPU mask changed; cause not established')
        except Exception as error:
            report['cleanup_error'] = repr(error)
        save()
    if (report['status'] != 'descriptors-verified' or not report['cleanup_confirmed'] or
            not report['temporary_cleanup_confirmed'] or 'cleanup_error' in report):
        raise RuntimeError('query/cleanup not fully verified; preserve operation.json, do not repeat insertion')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--serial',required=True)
    parser.add_argument('--adb',default='adb')
    parser.add_argument('--ack-kernel-module-risk',action='store_true')
    args = parser.parse_args()
    if not args.ack_kernel_module_risk:
        parser.error('--ack-kernel-module-risk is required; nothing sent')
    try:
        result = collect(args.out,args.module,args.serial,args.adb)
    except (OSError,ValueError,RuntimeError) as error:
        parser.exit(1,str(error)+'\n')
    print(json.dumps({key:result[key] for key in ['status','insertion_attempts','cleanup_confirmed','temporary_cleanup_confirmed']},indent=2))
