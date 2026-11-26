#!/usr/bin/env python3
"""Read-only ADB collection. Does not reboot, mount, delete or write on device."""
import argparse, hashlib, json, subprocess
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=False)
commands = {
 'root.txt': 'id',
 'boot-id.txt': 'cat /proc/sys/kernel/random/boot_id',
 'uptime.txt': 'cat /proc/uptime',
 'mounts.txt': 'cat /proc/mounts',
 'consoles.txt': 'cat /proc/consoles',
 'pstore-list.txt': 'ls -la /sys/fs/pstore',
 'ramoops-driver.txt': 'ls -la /sys/bus/platform/drivers/ramoops',
 'kernel-log.txt': 'dmesg',
 'pstore.tar': 'tar -C /sys/fs/pstore -cf - .',
}
manifest = {}
for name, command in commands.items():
    try:
        r = subprocess.run(['adb', 'exec-out', 'su', '-c', command],
                           capture_output=True, timeout=30)
        data, err, status = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        data, err, status = e.stdout or b'', e.stderr or b'', 'timeout'
    except OSError as e:
        data, err, status = b'', str(e).encode(), 'launch-error'
    (a.out / name).write_bytes(data)
    (a.out / (name + '.stderr')).write_bytes(err)
    manifest[name] = {'status': status, 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest()}
    (a.out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(name, status, len(data), flush=True)
    if name == 'root.txt' and (status != 0 or b'uid=0(' not in data):
        raise SystemExit('Root indisponivel; consulte root.txt e root.txt.stderr')
print('Captura concluida; confira manifest.json. Nenhum reboot solicitado.')
