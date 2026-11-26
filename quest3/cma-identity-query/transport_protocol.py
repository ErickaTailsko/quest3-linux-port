#!/usr/bin/env python3
"""Completion framing only. No ADB, subprocess runner or live device adapter."""
import re


LIMIT = 1024 * 1024
PREFIX = b'\nERIS_CMA_DONE '


class RemoteCommandFailed(RuntimeError):
    """A matching completion frame proved the foreground shell exited nonzero."""

    def __init__(self, returncode):
        self.returncode = returncode
        super().__init__('remote command completed with status ' + str(returncode))


def validate_token(token):
    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{32}', token):
        raise ValueError('invalid completion token')


def render(command, token):
    """Text for a future reviewed root-shell adapter, never executed here.

    The command runs in a foreground subshell, so its `exit`/`set -e` cannot
    skip the outer completion frame. No background jobs are permitted by the
    controller's fixed command set. This is not a process-tree quiescence proof.
    """
    validate_token(token)
    if not isinstance(command, str) or not command or '\0' in command or len(command) > 16384:
        raise ValueError('invalid command')
    return ('(\n' + command + '\n)\n_eris_status=$?\n'
            "printf '\\nERIS_CMA_DONE " + token + " %s\\n' \"$_eris_status\"\n")


def parse(data, token):
    validate_token(token)
    if not isinstance(data, bytes) or len(data) > LIMIT or data.count(PREFIX) != 1:
        raise ValueError('missing, duplicate or oversized completion frame')
    start = data.index(PREFIX)
    frame = data[start:]
    match = re.fullmatch(rb'\nERIS_CMA_DONE ' + token.encode() + rb' (0|[1-9][0-9]{0,2})\n', frame)
    if not match or int(match[1]) > 255:
        raise ValueError('invalid, foreign or truncated completion frame')
    return data[:start], int(match[1])
