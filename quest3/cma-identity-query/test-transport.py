#!/usr/bin/env python3
"""Protocol framing tests using local harmless shell commands; no ADB/device I/O."""
import subprocess
from transport_protocol import LIMIT, PREFIX, parse, render


token = '0123456789abcdef'*2
for command, output, status in (
        ("printf 'hello'", b'hello', 0), ("printf 'hello\\n'", b'hello\n', 0),
        ('exit 23', b'', 23), ('set -e; false; echo SHOULD_NOT_RUN', b'', 1),
        ("printf 'partial'; exit 125", b'partial', 125)):
    result = subprocess.run(['/bin/sh', '-c', render(command, token)], capture_output=True, timeout=5)
    # The wrapper itself can exit zero even for a failed remote action. Only
    # the matching framed status establishes that action's completion/result.
    assert result.returncode == 0
    assert parse(result.stdout, token) == (output, status)

frame = PREFIX+token.encode()+b' 0\n'
for wire in (b'', b'raw stdout without fence', frame[:-1], frame+b'extra', frame+frame,
             frame.replace(token.encode(), b'f'*32), frame.replace(b' 0\n', b' 256\n'),
             frame.replace(b' 0\n', b' -1\n'), frame.replace(b' 0\n', b' 00\n'),
             b'x'*LIMIT+frame, None, 'not bytes'):
    try:
        parse(wire, token)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid completion accepted')
for bad_token in ('', 'A'*32, 'f'*31, 'f'*32+'; echo injected', None):
    for function, first in ((parse, frame), (render, 'true')):
        try:
            function(first, bad_token)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid token accepted')
print('PASS local completion protocol: exact nonce/status/limits, failure fences, no device adapter')
