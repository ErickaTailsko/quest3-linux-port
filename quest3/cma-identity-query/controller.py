#!/usr/bin/env python3
"""Host-testable one-shot controller. No live transport or reviewed binary enabled."""
import base64
import hashlib
import json
import os
import re
import uuid

from transport_protocol import RemoteCommandFailed, parse as parse_completion


NAME = 'q3_cma_identity'
SYSFS = '/sys/kernel/' + NAME
EXPECTED_MODULE = None  # Must remain disarmed until a separate binary review.
EXPECTED_RELEASE = b'5.10.246-gd7102a837402'
EXPECTED_CONFIG_GZ = 'a8fc09c1b78fb07216b9dfaef2f91a8108780471aa8e157589924ac8042c6260'
EXPECTED_DTB = '7b377234c27f8c4c0d3ba8f48a1502e5aaff5f85ec476d8e90dc4ca22aca5077'


def validate_report(data, attempt):
    if not isinstance(data, bytes) or len(data) > 1024:
        raise ValueError('oversized or non-byte report')
    if not re.fullmatch(r'[0-9a-f]{32}', attempt):
        raise ValueError('invalid attempt identifier')
    text = data.decode('ascii')
    pattern = (r'schema=1 attempt=' + attempt + r'\n'
               r'identity_observed=([01]) error=(0|-[1-9][0-9]{0,3}) stage=([1-7]) '
               r'descriptor_valid=([01]) pointer_match=([01]) name_match=([01]) stable=([01]) '
               r'allocator_called=0 availability_proven=0 ownership_acquired=0 '
               r'allocation_experiment_ready=0 boot_ready=0\n')
    match = re.fullmatch(pattern, text)
    if not match:
        raise ValueError('unexpected report schema, token or claims')
    observed, error, stage, descriptor, pointer, name, stable = map(int, match.groups())
    if (observed != (stage == 7) or (error == 0) != bool(observed) or
            [descriptor, pointer, name, stable] != [int(stage >= n) for n in (4, 5, 6, 7)]):
        raise ValueError('inconsistent identity stages')
    return dict(identity_observed=bool(observed), error=error, stage=stage,
                descriptor_valid=bool(descriptor), pointer_match=bool(pointer),
                name_match=bool(name), stable=bool(stable), allocator_called=False,
                availability_proven=False, ownership_acquired=False,
                allocation_experiment_ready=False, boot_ready=False)


def collect(out, module, *, transport, consent=False):
    """transport(command, token) returns completion-framed bytes or raises.

    Only synthetic transports are supplied by this project at this stage.
    Existing evidence directories are never resumed or overwritten.
    """
    if consent is not True or EXPECTED_MODULE is None:
        raise ValueError('disarmed: consent and separately reviewed module required')
    payload = module.read_bytes()
    if hashlib.sha256(payload).hexdigest() != EXPECTED_MODULE:
        raise ValueError('unreviewed module; transport not called')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    attempt = uuid.uuid4().hex
    remote = '/data/local/tmp/eris-cma-identity-' + attempt + '.ko'
    report = dict(schema=2, status='incomplete', attempt=attempt, remote_path=remote,
                  module_sha256=EXPECTED_MODULE, transport_state='idle',
                  query_verified=False,
                  insertion_attempts=0, cleanup_confirmed=False,
                  removal_attempts=0, deletion_attempts=0, temporary_state='unattempted',
                  temporary_cleanup_confirmed=False, allocator_called=False,
                  availability_proven=False, ownership_acquired=False,
                  allocation_experiment_ready=False, boot_ready=False,
                  cpu_pause_requested=False, page_acquisition_requested=False,
                  reboot_requested=False, events=[])
    boot = None
    temporary_attempted = False
    temporary_owned = False
    baseline_absent = False
    journal_broken = False

    def sync_directory(path):
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    sync_directory(out.parent)

    def save():
        nonlocal journal_broken
        if journal_broken:
            raise RuntimeError('journal failure latched; no more transport')
        try:
            with (out/'operation.json.new').open('w') as stream:
                stream.write(json.dumps(report, indent=2) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(out/'operation.json.new', out/'operation.json')
            sync_directory(out)
        except BaseException:
            journal_broken = True
            raise

    def read(command):
        if journal_broken or report.get('safety_stop') or report['transport_state'] != 'idle':
            raise RuntimeError('unresolved transport/journal state; no more commands')
        token = uuid.uuid4().hex
        event = dict(command=command, token=token, completed=False)
        report['events'].append(event)
        report['transport_state'] = 'pending'
        save()
        try:
            wire = transport(command, token)
            if isinstance(wire, bytes):
                event['reply_bytes'] = len(wire)
                event['unverified_reply_prefix'] = wire[:1024].decode(errors='replace')
            value, returncode = parse_completion(wire, token)
        except BaseException as error:
            event['error'] = type(error).__name__
            report['transport_state'] = 'uncertain'
            try:
                save()
            except BaseException:
                pass  # The prior durable pending event already forbids replay.
            raise
        event.update(completed=True, returncode=returncode, stdout=value.decode(errors='replace'))
        report['transport_state'] = 'idle'
        if returncode in (125, 126):
            report['safety_stop'] = 'remote guard/reserved status rejected operation'
        save()
        if returncode:
            raise RemoteCommandFailed(returncode)
        return value

    def absent(path):
        if read('if test -e ' + path + ' || test -L ' + path +
                '; then echo PRESENT; else echo ABSENT; fi') != b'ABSENT\n':
            raise RuntimeError('absence not confirmed: ' + path)

    def modules():
        return [line.split()[0] for line in read('cat /proc/modules').splitlines() if line.split()]

    def boot_id():
        value = read('cat /proc/sys/kernel/random/boot_id').strip()
        if not re.fullmatch(rb'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
            raise ValueError('invalid boot identity')
        return value

    def same_boot():
        value = boot_id()
        if boot is None or value != boot:
            raise RuntimeError('boot changed/unknown; no cleanup in a new boot')
        return value

    def guarded(action):
        if boot is None:
            raise RuntimeError('no confirmed boot for mutation')
        return ('if test "$(cat /proc/sys/kernel/random/boot_id)" = ' + boot.decode() +
                '; then ' + action + '; else exit 125; fi')

    def runtime_hashes():
        for path, expected in (('/proc/config.gz', EXPECTED_CONFIG_GZ),
                               ('/sys/firmware/fdt', EXPECTED_DTB)):
            fields = read('sha256sum ' + path).split()
            if len(fields) != 2 or fields[0].decode('ascii') != expected or fields[1].decode('ascii') != path:
                raise ValueError('runtime config/DT mismatch')

    def online_cpus():
        value = read('cat /sys/devices/system/cpu/online').strip()
        if len(value) > 128 or not re.fullmatch(rb'[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*', value):
            raise ValueError('invalid online CPU mask')
        previous = -1
        for interval in value.decode('ascii').split(','):
            endpoints = interval.split('-')
            low, high = int(endpoints[0]), int(endpoints[-1])
            if low <= previous or low > high or high > 4095 or any(str(int(v)) != v for v in endpoints):
                raise ValueError('noncanonical online CPU mask')
            previous = high
        return value.decode('ascii')

    def snapshot():
        data = read('head -c 1025 ' + SYSFS + '/report')
        parsed = validate_report(data, attempt)
        report['report_sha256'] = hashlib.sha256(data).hexdigest()
        return parsed

    save()
    try:
        if not read('id').startswith(b'uid=0('):
            raise ValueError('existing root not confirmed')
        if read('uname -r').strip() != EXPECTED_RELEASE:
            raise ValueError('unexpected kernel release')
        boot = boot_id()
        report['boot_id_before'] = boot.decode()
        runtime_hashes()
        report['cpus_before'] = online_cpus()
        if NAME.encode() in modules():
            raise ValueError('preexisting module; never assume ownership')
        absent('/sys/module/' + NAME)
        absent(SYSFS)
        absent(remote)
        baseline_absent = True
        temporary_attempted = True
        report['temporary_state'] = 'pending'
        if read(guarded('umask 077; set -C; if ( : > ' + remote +
                ' ); then echo CREATED; else echo NOT_CREATED; fi')) != b'CREATED\n':
            raise RuntimeError('temporary file creation not confirmed')
        temporary_owned = True
        report['temporary_state'] = 'owned'
        for offset in range(0, len(payload), 4096):
            encoded = base64.b64encode(payload[offset:offset+4096]).decode('ascii')
            read(guarded('printf %s ' + encoded + ' | base64 -d | dd of=' + remote +
                 ' bs=4096 seek=' + str(offset//4096) + ' conv=notrunc 2>/dev/null'))
        if read('wc -c ' + remote).split() != [str(len(payload)).encode(), remote.encode()]:
            raise ValueError('remote length mismatch')
        if read('sha256sum ' + remote).split() != [EXPECTED_MODULE.encode(), remote.encode()]:
            raise ValueError('remote hash mismatch')
        same_boot()
        if NAME.encode() in modules():
            raise RuntimeError('module appeared during transfer; do not insert')
        absent('/sys/module/' + NAME)
        absent(SYSFS)
        report['insertion_attempts'] = 1
        save()  # Durable intent BEFORE the single, possibly uncertain operation.
        read(guarded('insmod ' + remote + ' inspect=1 attempt=' + attempt))
        report['identity_snapshot'] = snapshot()
        same_boot()
        runtime_hashes()
        if not report['identity_snapshot']['identity_observed']:
            raise ValueError('identity rejected by module')
        report['query_verified'] = True
    except Exception as error:
        report['error'] = repr(error)
    finally:
        try:
            if journal_broken or report.get('safety_stop') or report['transport_state'] != 'idle':
                raise RuntimeError('completion/durability unknown; no automatic reconciliation or cleanup')
            same_boot()
            if not baseline_absent:
                raise RuntimeError('preflight incomplete; no unowned cleanup')
            if NAME.encode() in modules():
                if not report['insertion_attempts']:
                    raise RuntimeError('unowned module appeared; do not unload')
                # Only proven prior completion reaches cleanup. Current token
                # and schema must match; invalid report => retain for review.
                snapshot()
                same_boot()
                report['removal_attempts'] = 1
                read(guarded('if test "$(head -n 1 ' + SYSFS +
                             '/report)" = "schema=1 attempt=' + attempt +
                             '"; then rmmod ' + NAME + '; else exit 126; fi'))
            if NAME.encode() in modules():
                raise RuntimeError('module remains present')
            absent('/sys/module/' + NAME)
            absent(SYSFS)
            report['cleanup_confirmed'] = True
            same_boot()
            if temporary_attempted and not temporary_owned:
                raise RuntimeError('temporary file ownership uncertain; no blind deletion')
            if temporary_owned:
                report['deletion_attempts'] = 1
                read(guarded('rm -f ' + remote))
                absent(remote)
                report['temporary_state'] = 'removed'
            report['temporary_cleanup_confirmed'] = True
            report['cpus_after'] = online_cpus()
            if report['cpus_after'] != report['cpus_before']:
                raise RuntimeError('online CPU mask changed; cause not established')
            report['boot_id_after'] = same_boot().decode()
        except Exception as error:
            report['cleanup_error'] = repr(error)
        if 'error' in report or 'cleanup_error' in report or report['transport_state'] != 'idle':
            report['status'] = 'recovery-required' if 'cleanup_error' in report else 'failed-clean'
        if not journal_broken:
            save()
    if (not report['query_verified'] or 'error' in report or
            'cleanup_error' in report or not report['cleanup_confirmed'] or
            not report['temporary_cleanup_confirmed']):
        raise RuntimeError('query/cleanup incomplete; preserve journal, never repeat insertion')
    report['status'] = 'identity-observed'
    save()  # Terminal success only after the query AND cleanup were confirmed.
    return report


if __name__ == '__main__':
    raise SystemExit('Host-testable controller only; no live transport or reviewed module enabled.')
