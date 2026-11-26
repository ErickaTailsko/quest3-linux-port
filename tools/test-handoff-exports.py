#!/usr/bin/env python3
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('audit', Path(__file__).with_name('audit-handoff-exports.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
loader = 'lookup("private"); lookup("private"); lookup("kernel_restart");'
exports = '0x12345678 kernel_restart vmlinux EXPORT_SYMBOL_GPL\n'
result = module.audit(loader, exports)
assert result['private_lookup_count'] == 2
assert result['nonexported_lookup_count'] == 1
assert result['source_lookups'][0]['exported']
assert not result['source_lookups'][1]['exported']
assert not result['cfi_compatible_handoff_implemented'] and not result['execute_authorized']
assert result['exported_does_not_mean_context_safe']
for invalid in ['', 'bad line', exports + exports]:
    try:
        module.audit(loader, invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid export table accepted')
print('PASS export inventory: deduplication, missing exports, malformed/duplicate tables and no context-safety or execution claim')
