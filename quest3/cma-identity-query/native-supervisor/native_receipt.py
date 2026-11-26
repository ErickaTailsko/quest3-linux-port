#!/usr/bin/env python3
"""Bounded native-v2 receipt parser only; no filesystem/transport/resume API."""
import base64
from dataclasses import asdict
import hashlib
import json

MAX_RECORD = 190000
MAX_CAPTURE = 65536


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate receipt key')
        value[key] = item
    return value


def parse(data, expected_intent):
    if not isinstance(data, bytes) or len(data) >= MAX_RECORD:
        raise ValueError('invalid/oversized native receipt')
    value = json.loads(data, object_pairs_hook=unique)
    fields = {'schema', 'intent', 'foreground_reaped', 'termination_kind', 'termination_value',
              'exec_errno', 'supervisor_interrupted', 'stdout_b64', 'stdout_size', 'stdout_sha256',
              'stderr_b64', 'stderr_size', 'stderr_sha256', 'tree_quiescence_proven', 'safe_to_mutate'}
    if (not isinstance(value, dict) or set(value) != fields or
            type(value['schema']) is not int or value['schema'] != 2 or
            value['intent'] != asdict(expected_intent) or value['foreground_reaped'] is not True or
            value['tree_quiescence_proven'] is not False or value['safe_to_mutate'] is not False or
            type(value['supervisor_interrupted']) is not bool or type(value['exec_errno']) is not int or
            not 0 <= value['exec_errno'] <= 4095 or type(value['termination_value']) is not int):
        raise ValueError('native receipt identity/schema/claims mismatch')
    if value['termination_kind'] == 'exit':
        valid = 0 <= value['termination_value'] <= 255
    elif value['termination_kind'] == 'signal':
        valid = 1 <= value['termination_value'] <= 64 and not value['exec_errno']
    else:
        valid = False
    if not valid or value['exec_errno'] and (value['termination_kind'], value['termination_value']) != ('exit', 127):
        raise ValueError('invalid foreground termination/exec outcome')
    result = dict(termination_kind=value['termination_kind'], termination_value=value['termination_value'],
                  exec_errno=value['exec_errno'], supervisor_interrupted=value['supervisor_interrupted'],
                  receipt_matches_intent=True, safe_to_mutate=False, automatic_resume_allowed=False,
                  tree_quiescence_proven=False, lease_free_verified=False, boot_ready=False)
    for stream in ('stdout', 'stderr'):
        if (type(value[stream+'_size']) is not int or not 0 <= value[stream+'_size'] <= MAX_CAPTURE or
                not isinstance(value[stream+'_b64'], str)):
            raise ValueError('invalid output length/encoding')
        decoded = base64.b64decode(value[stream+'_b64'], validate=True)
        if len(decoded) != value[stream+'_size'] or hashlib.sha256(decoded).hexdigest() != value[stream+'_sha256']:
            raise ValueError('output hash/length mismatch')
        result[stream] = decoded
    return result
