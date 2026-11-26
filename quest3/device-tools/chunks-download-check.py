#!/usr/bin/env python3
"""Read existing world-readable DTB copy via small ADB shell/base64 chunks."""
import base64, hashlib, re, subprocess, time
from pathlib import Path
remote = "/data/local/tmp/quest3-live-copy.dtb"
out = Path.home() / "quest3-live-chunks.dtb"
def adb(command):
    r = subprocess.run(["adb", "shell", command], capture_output=True, timeout=20)
    if r.returncode or not r.stdout.strip():
        raise RuntimeError("ADB sem resposta válida: " + r.stderr.decode(errors="replace")[:200])
    return r.stdout
size = int(adb("wc -c " + remote).split()[0])
expected = adb("sha256sum " + remote).split()[0].decode()
if not 40 <= size <= 4*1024*1024 or not re.fullmatch("[0-9a-f]{64}", expected):
    raise SystemExit("Metadados inválidos; nada salvo.")
if out.exists():
    if out.stat().st_size == size and hashlib.sha256(out.read_bytes()).hexdigest() == expected:
        print("Arquivo já existe e está conferido:", out)
        raise SystemExit(0)
    raise SystemExit("Destino existente diferente; nada sobrescrito: " + str(out))
block = 16384
count = (size + block - 1) // block
data = bytearray()
for i in range(count):
    for attempt in range(3):
        try:
            command = "dd if=" + remote + " bs=16384 skip=" + str(i) + " count=1 2>/dev/null | base64"
            chunk = base64.b64decode(b"".join(adb(command).split()), validate=True)
            if len(chunk) != min(block, size - i*block):
                raise ValueError("Bloco incompleto")
            break
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
            if attempt == 2:
                raise SystemExit("Falha no bloco " + str(i+1) + "; nada salvo: " + str(e))
            time.sleep(1)
    data.extend(chunk)
    print("Bloco", i+1, "/", count, flush=True)
if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
    raise SystemExit("Integridade falhou; nada salvo.")
if data[:4] != bytes.fromhex("d00dfeed"):
    raise SystemExit("Cabeçalho FDT inválido; nada salvo.")
with out.open("xb") as f:
    f.write(data)
print("DTB salvo e SHA256 conferido:", out)
print("SHA256:", expected)
