#!/usr/bin/env python3
"""Mock-only transport, including uncertain operations and ownership tokens."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

path = Path(__file__).with_name('controller.py')
spec = importlib.util.spec_from_file_location('identity_controller', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.EXPECTED_MODULE is None  # Production entry point stays disarmed.


def fixture(attempt, stage=7):
    flags = [int(stage >= n) for n in (4, 5, 6, 7)]
    return (f'schema=1 attempt={attempt}\nidentity_observed={int(stage == 7)} '
            f'error={0 if stage == 7 else -22} stage={stage} descriptor_valid={flags[0]} '
            f'pointer_match={flags[1]} name_match={flags[2]} stable={flags[3]} '
            'allocator_called=0 availability_proven=0 ownership_acquired=0 '
            'allocation_experiment_ready=0 boot_ready=0\n').encode()


token = 'a'*32
good = fixture(token)
assert m.validate_report(good, token)['identity_observed']
for stage in range(1, 7):
    assert not m.validate_report(fixture(token, stage), token)['identity_observed']
for data in [good+b'\n', good[:-1], b'x'*1025, good.replace(b'schema=1', b'schema=2'),
             good.replace(b'error=0', b'error=-22'), good.replace(b'stable=1', b'stable=0'),
             good.replace(b'identity_observed=1', b'identity_observed=0'),
             good.replace(b'allocator_called=0', b'allocator_called=1'),
             good.replace(b'boot_ready=0', b'boot_ready=1'), fixture('b'*32),
             good.replace(b'name_match=1', b'name_match=2'), good.replace(b'stage=7', b'stage=8'),
             good.replace(b'schema=1', b'\xff')]:
    try:
        m.validate_report(data, token)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid report accepted')


class FakeTransport:
    def __init__(self, out, mode='ok'):
        self.out = out
        self.mode = mode
        self.calls = []
        self.insertions = self.removals = self.deletions = self.boot_reads = 0
        self.report_reads = 0
        self.loaded = mode == 'preexisting'
        self.uploaded = False
        self.blob = bytearray()
        self.remote = None
        self.attempt = None
        self.deferred = None

    def __call__(self, command, token):
        self.calls.append(command)
        persisted = json.loads((self.out/'operation.json').read_text())
        assert persisted['transport_state'] == 'pending'
        assert persisted['events'][-1]['command'] == command and persisted['events'][-1]['token'] == token
        assert not persisted['events'][-1]['completed']
        actual = command
        guarded = re.fullmatch(r'if test "\$\(cat /proc/sys/kernel/random/boot_id\)" = '
                              r'([0-9a-f-]+); then (.*); else exit 125; fi', command)
        if guarded:
            assert guarded[1] == '00000000-0000-0000-0000-000000000001'
            actual = guarded[2]
            if self.mode == 'boot-in-command' and actual.startswith('insmod '):
                return b'\nERIS_CMA_DONE '+token.encode()+b' 125\n'
            owner = re.fullmatch(r'if test "\$\(head -n 1 ' + re.escape(m.SYSFS) +
                                 r'/report\)" = "schema=1 attempt=([0-9a-f]{32})"; '
                                 r'then rmmod '+m.NAME+r'; else exit 126; fi', actual)
            if owner:
                assert owner[1] == self.attempt
                if self.mode == 'token-in-command':
                    return b'\nERIS_CMA_DONE '+token.encode()+b' 126\n'
                actual = 'rmmod '+m.NAME
        else:
            assert not actual.startswith(('insmod ', 'rmmod ', 'rm -f ', 'umask ', 'printf '))
        try:
            value = self.execute(actual)
            code = 0
        except m.RemoteCommandFailed as error:
            value, code = b'', error.returncode
        frame = value+b'\nERIS_CMA_DONE '+token.encode()+b' '+str(code).encode()+b'\n'
        if self.mode == 'bad-frame' and actual.startswith('insmod '):
            return frame[:-1]
        if self.mode == 'foreign-frame' and actual.startswith('insmod '):
            return frame.replace(token.encode(), b'f'*32)
        return frame

    def execute(self, command):
        if command == 'id':
            return b'uid=0(root) gid=0(root)\n' if self.mode != 'no-root' else b'uid=2000(shell)\n'
        if command == 'uname -r':
            return (m.EXPECTED_RELEASE if self.mode != 'release' else b'other') + b'\n'
        if command == 'cat /proc/sys/kernel/random/boot_id':
            self.boot_reads += 1
            if self.mode == 'invalid-boot':
                return b'bad\n'
            changed = ((self.mode == 'boot-change' and self.insertions) or
                       (self.mode == 'boot-before-unload' and self.boot_reads >= 5) or
                       (self.mode == 'boot-before-insert' and self.boot_reads > 1))
            return b'00000000-0000-0000-0000-00000000000' + (b'2' if changed else b'1') + b'\n'
        if command.startswith('sha256sum /proc/') or command.startswith('sha256sum /sys/'):
            target = command.split()[1]
            value = m.EXPECTED_CONFIG_GZ if target == '/proc/config.gz' else m.EXPECTED_DTB
            if self.mode == 'config' or (self.mode == 'post-config' and self.insertions):
                value = '0'*64
            if self.mode == 'dt' and target == '/sys/firmware/fdt':
                value = '0'*64
            return (value + '  ' + target + '\n').encode()
        if command == 'cat /sys/devices/system/cpu/online':
            if self.mode == 'invalid-cpus':
                return b''
            if self.mode.startswith('invalid-cpus:'):
                return self.mode.split(':', 1)[1].encode()+b'\n'
            return b'0-4\n' if self.mode == 'cpu-change' and self.insertions else b'0-5\n'
        if command == 'cat /proc/modules':
            if self.mode == 'appeared-module' and self.blob:
                self.loaded = True
            return (m.NAME + ' 4096 0 - Live 0\n').encode() if self.loaded else b''
        if command.startswith('if test -e '):
            match = re.fullmatch(r'if test -e ([^; ]+) \|\| test -L \1; then echo PRESENT; else echo ABSENT; fi', command)
            assert match
            target = match[1]
            if target == m.SYSFS:
                exists = self.loaded or self.mode == 'preexisting-sysfs'
            elif target == '/sys/module/' + m.NAME:
                exists = self.loaded or self.mode == 'preexisting-sysmodule'
            else:
                assert re.fullmatch(r'/data/local/tmp/eris-cma-identity-[0-9a-f]{32}\.ko', target)
                self.remote = target
                self.attempt = target.rsplit('-', 1)[1][:-3]
                exists = self.uploaded or self.mode in ('preexisting-temp', 'preexisting-symlink')
            return b'PRESENT\n' if exists else b'ABSENT\n'
        if command == ('umask 077; set -C; if ( : > ' + self.remote +
                       ' ); then echo CREATED; else echo NOT_CREATED; fi'):
            assert not self.uploaded
            if self.mode == 'create-denied':
                return b'NOT_CREATED\n'
            self.uploaded = True
            if self.mode == 'lost-create':
                raise TimeoutError('creation reply lost')
            return b'CREATED\n'
        if command.startswith('printf %s '):
            match = re.fullmatch(r'printf %s ([A-Za-z0-9+/=]+) \| base64 -d \| dd of=' +
                                 re.escape(self.remote) + r' bs=4096 seek=(\d+) conv=notrunc 2>/dev/null', command)
            assert match and self.uploaded
            chunk = base64.b64decode(match[1], validate=True)
            assert int(match[2])*4096 == len(self.blob) and len(chunk) <= 4096
            if self.mode == 'late-chunk':
                self.deferred = chunk
                raise TimeoutError('chunk still executing remotely')
            self.blob.extend(chunk)
            if self.mode == 'lost-chunk':
                raise TimeoutError('chunk reply lost')
            return b''
        if command == 'wc -c ' + self.remote:
            size = len(self.blob) if self.mode != 'length' else 1
            return (str(size) + ' ' + self.remote + '\n').encode()
        if command == 'sha256sum ' + self.remote:
            value = hashlib.sha256(self.blob).hexdigest() if self.mode != 'hash' else '0'*64
            return (value + '  ' + self.remote + '\n').encode()
        if command.startswith('insmod '):
            assert command == 'insmod ' + self.remote + ' inspect=1 attempt=' + self.attempt
            assert not self.loaded and self.uploaded and hashlib.sha256(self.blob).hexdigest() == m.EXPECTED_MODULE
            persisted = json.loads((self.out/'operation.json').read_text())
            assert persisted['insertion_attempts'] == 1 and persisted['attempt'] == self.attempt
            assert persisted['transport_state'] == 'pending' and not persisted['events'][-1]['completed']
            self.insertions += 1
            if self.mode == 'insert-failed':
                raise m.RemoteCommandFailed(1)
            if self.mode == 'late-insert':
                self.deferred = 'insert'
                raise TimeoutError('insmod still executing remotely')
            self.loaded = True
            if self.mode == 'lost-insert':
                raise TimeoutError('insertion reply lost')
            if self.mode == 'interrupted':
                raise KeyboardInterrupt('interrupted while remote may still run')
            return b''
        if command == 'head -c 1025 ' + m.SYSFS + '/report':
            assert self.loaded
            self.report_reads += 1
            if self.mode == 'lost-report' and self.report_reads == 1:
                raise TimeoutError('report reply lost')
            if self.mode == 'bad-report':
                return b'truncated\n'
            if self.mode == 'foreign-token':
                return fixture('b'*32)
            return fixture(self.attempt, 4 if self.mode == 'rejected' else 7)
        if command == 'rmmod ' + m.NAME:
            assert self.loaded and self.insertions == 1 and self.mode != 'foreign-token'
            self.removals += 1
            if self.mode == 'rmmod-failed':
                raise m.RemoteCommandFailed(1)
            self.loaded = False
            if self.mode == 'lost-rmmod':
                raise TimeoutError('rmmod reply lost')
            return b''
        if command == 'rm -f ' + self.remote:
            assert self.uploaded
            self.deletions += 1
            self.uploaded = False
            if self.mode == 'lost-delete':
                raise TimeoutError('delete reply lost')
            return b''
        raise AssertionError('unexpected remote command: ' + command)


with tempfile.TemporaryDirectory(prefix='q3-cma-controller-') as temporary:
    root = Path(temporary)
    module = root/'fixture.ko'
    module.write_bytes(b'synthetic-module'*650)
    fake = FakeTransport(root/'disarmed')
    try:
        m.collect(fake.out, module, transport=fake, consent=True)
    except ValueError:
        pass
    else:
        raise AssertionError('production controller was armed')
    assert not fake.calls and not fake.out.exists()
    m.EXPECTED_MODULE = hashlib.sha256(module.read_bytes()).hexdigest()
    for denied in (False, None, 1, 'yes'):
        try:
            m.collect(fake.out, module, transport=fake, consent=denied)
        except ValueError:
            pass
        else:
            raise AssertionError('consent not required')
        assert not fake.calls and not fake.out.exists()
    fake = FakeTransport(root/'ok')
    result = m.collect(fake.out, module, transport=fake, consent=True)
    assert result['status'] == 'identity-observed' and result['identity_snapshot']['identity_observed']
    assert result['cleanup_confirmed'] and result['temporary_cleanup_confirmed']
    assert fake.insertions == fake.removals == fake.deletions == 1 and not fake.loaded and not fake.uploaded
    assert all(result[key] is False for key in ('allocator_called', 'availability_proven',
               'ownership_acquired', 'allocation_experiment_ready', 'boot_ready'))
    before = (fake.out/'operation.json').read_bytes()
    fake2 = FakeTransport(fake.out)
    try:
        m.collect(fake2.out, module, transport=fake2, consent=True)
    except FileExistsError:
        pass
    else:
        raise AssertionError('evidence reused')
    assert not fake2.calls and before == (fake.out/'operation.json').read_bytes()
    modes = ['no-root', 'release', 'invalid-boot', 'invalid-cpus', 'config', 'dt', 'preexisting',
             'preexisting-sysfs', 'preexisting-sysmodule', 'preexisting-temp', 'preexisting-symlink',
             'lost-create', 'create-denied', 'lost-chunk', 'length', 'hash', 'boot-before-insert',
             'appeared-module', 'boot-before-unload', 'lost-report', 'boot-in-command', 'token-in-command',
             'bad-frame', 'foreign-frame', 'late-insert', 'late-chunk',
             'lost-insert', 'insert-failed', 'bad-report', 'foreign-token', 'rejected',
             'boot-change', 'post-config', 'rmmod-failed', 'lost-rmmod', 'lost-delete', 'cpu-change']
    modes += ['invalid-cpus:'+value for value in ('5-1', '0-3,2-5', '0,0', '00-5', '0-4096')]
    for mode in modes:
        fake = FakeTransport(root/mode, mode)
        try:
            m.collect(fake.out, module, transport=fake, consent=True)
        except RuntimeError:
            pass
        else:
            raise AssertionError('unsafe/incomplete state accepted: ' + mode)
        saved = json.loads((fake.out/'operation.json').read_text())
        assert saved['status'] != 'identity-observed'
        assert fake.insertions <= 1 and fake.removals <= 1 and fake.deletions <= 1
        if mode in ('bad-report', 'foreign-token', 'boot-change', 'boot-before-insert',
                    'appeared-module', 'boot-before-unload'):
            assert not fake.removals and not fake.deletions and 'cleanup_error' in saved
        if mode in ('rejected', 'post-config'):
            assert fake.removals == 1 and not fake.loaded and not fake.uploaded
            assert saved['cleanup_confirmed'] and saved['temporary_cleanup_confirmed']
        if mode in ('preexisting', 'preexisting-sysfs', 'preexisting-sysmodule', 'preexisting-temp',
                    'preexisting-symlink'):
            assert not fake.insertions and not fake.removals and not fake.deletions
        if mode == 'lost-create':
            assert fake.uploaded and not fake.deletions and 'cleanup_error' in saved
        if mode == 'create-denied':
            assert not fake.uploaded and not fake.deletions and 'cleanup_error' in saved
        if mode in ('length', 'hash', 'insert-failed'):
            assert not fake.loaded and not fake.uploaded
        if mode in ('boot-in-command', 'token-in-command'):
            assert saved['safety_stop'] and saved['transport_state'] == 'idle'
            assert not fake.deletions and fake.uploaded
            assert fake.calls[-1] == saved['events'][-1]['command']
        if mode in ('lost-create', 'lost-chunk', 'lost-insert', 'lost-report', 'lost-rmmod',
                    'lost-delete', 'late-insert', 'late-chunk', 'bad-frame', 'foreign-frame'):
            assert saved['transport_state'] == 'uncertain' and saved['status'] == 'recovery-required'
            assert not saved['events'][-1]['completed']
            assert fake.calls[-1] == saved['events'][-1]['command']  # No command after uncertainty.
        if mode in ('lost-insert', 'lost-report', 'late-insert', 'late-chunk', 'lost-chunk',
                    'bad-frame', 'foreign-frame'):
            assert not fake.removals and not fake.deletions and fake.uploaded
        if mode == 'late-insert':
            assert not fake.loaded and fake.deferred == 'insert'
            fake.loaded = True  # The remote command completes AFTER collect stopped.
            assert not saved['cleanup_confirmed'] and not fake.removals
        if mode == 'late-chunk':
            assert fake.deferred and not fake.blob
            fake.blob.extend(fake.deferred)
            assert fake.uploaded and not fake.deletions
    fake = FakeTransport(root/'interrupted', 'interrupted')
    try:
        m.collect(fake.out, module, transport=fake, consent=True)
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError('interrupt swallowed')
    saved = json.loads((fake.out/'operation.json').read_text())
    assert saved['transport_state'] == 'uncertain' and saved['status'] == 'recovery-required'
    assert fake.insertions == 1 and not fake.removals and not fake.deletions
    assert fake.calls[-1] == saved['events'][-1]['command']

    # Once persistence fails, even a later successful filesystem call must not
    # restart cleanup. The last durable nonterminal journal is all we can trust.
    for when in ('before-dispatch', 'after-completion', 'directory-fsync'):
        fake = FakeTransport(root/('journal-'+when))
        replace, fsync = m.os.replace, m.os.fsync
        failed = [False]

        def failing_replace(old, new):
            content = json.loads(Path(old).read_text())
            should_fail = (when == 'before-dispatch' and content['insertion_attempts'] == 1 or
                           when == 'after-completion' and fake.insertions == 1)
            if should_fail and not failed[0]:
                failed[0] = True
                raise OSError('injected journal replacement failure')
            return replace(old, new)

        def failing_fsync(descriptor):
            import stat
            if (when == 'directory-fsync' and fake.insertions == 1 and not failed[0] and
                    stat.S_ISDIR(m.os.fstat(descriptor).st_mode)):
                failed[0] = True
                raise OSError('injected directory durability failure')
            return fsync(descriptor)

        try:
            m.os.replace, m.os.fsync = failing_replace, failing_fsync
            try:
                m.collect(fake.out, module, transport=fake, consent=True)
            except RuntimeError:
                pass
            else:
                raise AssertionError('journal failure accepted')
        finally:
            m.os.replace, m.os.fsync = replace, fsync
        saved = json.loads((fake.out/'operation.json').read_text())
        assert failed[0] and saved['status'] != 'identity-observed'
        assert fake.insertions == (when != 'before-dispatch')
        assert not fake.removals and not fake.deletions and fake.uploaded
        if when == 'after-completion':
            assert saved['transport_state'] == 'pending'

    module.write_bytes(b'unreviewed')
    fake = FakeTransport(root/'bad-module')
    try:
        m.collect(fake.out, module, transport=fake, consent=True)
    except ValueError:
        pass
    else:
        raise AssertionError('unreviewed module accepted')
    assert not fake.calls and not fake.out.exists()
    result = subprocess.run([sys.executable, str(path)], capture_output=True, timeout=10)
    assert result.returncode != 0 and b'no live transport' in result.stderr
print('PASS identity controller: framed completion, no commands after uncertainty/interrupt/journal failure, guarded mutations, no retry; mocks only')
