#!/usr/bin/env python3
"""Rebuild hashes from staged/tracked Git paths; review secrets before staging."""
import hashlib
import argparse
import json
import subprocess
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--existing', action='store_true', help='Use the existing inventory when Git metadata is absent')
parser.add_argument('--include', action='append', default=[], help='Explicit repository-relative path to add with --existing')
args = parser.parse_args()
if args.existing:
    previous = json.loads((repo / 'manifests/files.json').read_text())
    paths = [entry['path'] for entry in previous['files']] + args.include
else:
    if args.include:
        parser.error('--include requires --existing')
    paths = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).decode().split('\0')
entries = []
for name in sorted(set(path for path in paths if path and path not in ('manifests/files.json', 'manifests/SHA256SUMS'))):
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise SystemExit('Refusing non-relative inventory path: ' + name)
    path = repo / name
    if not path.resolve().is_relative_to(repo):
        raise SystemExit('Refusing external link: ' + name)
    if path.is_dir() and path.is_symlink():
        entries.append({'path': name, 'kind': 'directory-symlink', 'target': str(path.readlink())})
        continue
    data = path.read_bytes()
    entry = {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    if path.is_symlink():
        entry.update(kind='symlink', target=str(path.readlink()))
    entries.append(entry)
scope = 'existing inventory plus explicit additions' if args.existing else 'tracked payload'
(repo / 'manifests/files.json').write_text(json.dumps({'scope': scope + '; inventory files excluded to avoid recursion', 'files': entries}, indent=2) + '\n')
(repo / 'manifests/SHA256SUMS').write_text(''.join(entry['sha256'] + '  ' + entry['path'] + '\n' for entry in entries if 'sha256' in entry))
print('Inventoried', len(entries), 'paths')
