#!/usr/bin/env python3
"""Upload this diagnostic module in idempotent 4KiB blocks; never insmod/reboot."""
import base64
import hashlib
import shlex
import subprocess
import time
import uuid
from pathlib import Path

EXPECTED = '403c9161a293cb6ce322c3ec0412268026c77e21b68f741c9436025f01993e2d'
TARGET = '/data/local/tmp/q3_ramoops_snapshot.ko'
BLOCK = 4096

def push(source):
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise RuntimeError('Local module SHA256 differs; nothing sent')
    def command(text, retry=False):
        for attempt in range(3 if retry else 1):
            try:
                result = subprocess.run(['adb', 'shell', 'su -c ' + shlex.quote(text)],
                                        capture_output=True, timeout=20)
                if result.returncode:
                    raise RuntimeError('ADB command failed')
                return result.stdout
            except (RuntimeError, subprocess.TimeoutExpired):
                if not retry or attempt == 2:
                    raise
                time.sleep(1)
    if b'uid=0(' not in command('id', retry=True):
        raise RuntimeError('Root identity not confirmed')
    # A unique temporary file prevents retries from truncating another upload.
    temporary = TARGET + '.part-' + uuid.uuid4().hex
    command('umask 077; : > ' + temporary)
    total = (len(data) + BLOCK - 1) // BLOCK
    for index in range(total):
        chunk = data[index * BLOCK:(index + 1) * BLOCK]
        encoded = base64.b64encode(chunk).decode('ascii')
        # Retrying rewrites the same offset. Never append an uncertain block.
        text = (f'printf %s {encoded} | base64 -d | '
                f'dd of={temporary} bs={BLOCK} seek={index} conv=notrunc 2>/dev/null')
        command(text, retry=True)
        if (index + 1) % 8 == 0 or index + 1 == total:
            print(f'Block {index + 1}/{total}', flush=True)
    fields = command('sha256sum ' + temporary, retry=True).split()
    if not fields or fields[0].decode('ascii', errors='replace') != EXPECTED:
        raise RuntimeError('Remote SHA256 differs; final file not installed')
    command('chmod 0644 ' + temporary + ' && mv -f ' + temporary + ' ' + TARGET)
    fields = command('sha256sum ' + TARGET, retry=True).split()
    if not fields or fields[0].decode('ascii', errors='replace') != EXPECTED:
        raise RuntimeError('Final SHA256 not confirmed')
    print('Upload verified:', TARGET)
    print('SHA256:', EXPECTED)
    print('Module not loaded; no reboot requested.')

if __name__ == '__main__':
    try:
        push(Path(__file__).resolve().with_name('q3_ramoops_snapshot.ko'))
    except Exception as error:
        raise SystemExit('Upload incomplete: ' + str(error))
