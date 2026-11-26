#!/usr/bin/env python3
"""Verify the publication inventory without executing any device script."""
import hashlib
import json
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
manifest = json.loads((repo / 'manifests/files.json').read_text())
failures = []
for entry in manifest['files']:
    path = repo / entry['path']
    if not path.resolve().is_relative_to(repo):
        failures.append(entry['path'] + ': outside repository')
        continue
    if entry.get('kind') == 'directory-symlink':
        if not path.is_symlink() or not path.is_dir() or str(path.readlink()) != entry['target']:
            failures.append(entry['path'] + ': directory link differs')
        continue
    try:
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            failures.append(entry['path'] + ': hash/size differs')
        if entry.get('kind') == 'symlink' and (not path.is_symlink() or str(path.readlink()) != entry['target']):
            failures.append(entry['path'] + ': link differs')
    except OSError:
        failures.append(entry['path'] + ': missing/unreadable')
for failure in failures:
    print('FAIL', failure)
print(f"Verified {len(manifest['files'])} paths; failures={len(failures)}")
raise SystemExit(bool(failures))
