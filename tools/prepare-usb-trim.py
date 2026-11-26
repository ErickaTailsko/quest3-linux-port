#!/usr/bin/env python3
"""Prepare a separate experimental target config; no device or kernel Image build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--profile', choices=('usb-trim1', 'usb-trim2', 'usb-trim3'), default='usb-trim1')
args = parser.parse_args()
out = args.out.resolve()
kernel = Path(os.environ.get('Q3_KERNEL', str(repo / '.work/kernel')))
bases = {'usb-trim1': 'ram-first-qmp.config', 'usb-trim2': 'usb-trim1.config',
         'usb-trim3': 'usb-trim2.config'}
base = repo / 'quest3/configs' / bases[args.profile]
fragments = [repo / 'quest3/usb-trim/trim1.fragment']
if args.profile in ('usb-trim2', 'usb-trim3'):
    fragments.append(repo / 'quest3/usb-trim/trim2.fragment')
if args.profile == 'usb-trim3':
    fragments.append(repo / 'quest3/usb-trim/trim3.fragment')
fragment_text = '\n'.join(path.read_text() for path in fragments)
revision = subprocess.check_output(['git', '-C', str(kernel), 'rev-parse', 'HEAD'], text=True).strip()
if revision != 'dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f':
    parser.error('unexpected kernel source revision')
dirty = subprocess.check_output(['git', '-C', str(kernel), 'status', '--porcelain', '--untracked-files=all'], text=True).rstrip('\n')
if dirty and not (dirty == ' M scripts/extract-cert.c' and
                  hashlib.sha256((kernel / 'scripts/extract-cert.c').read_bytes()).hexdigest() ==
                  '28b8eb37b33dd372d2d189687b2edc6bec8660d784fc3fb9fc4425f295a4ea0b'):
    parser.error('unreviewed source changes; preserve and review before preparing')
if out.exists():
    parser.error('output directory already exists; preserve previous work')
out.mkdir(parents=True)
(out / '.config').write_bytes(base.read_bytes())
(out / 'baseline.config').write_bytes(base.read_bytes())
disabled = list(dict.fromkeys(re.findall(r'^# CONFIG_(\w+) is not set$', fragment_text, re.M)))
if not disabled:
    parser.error('empty reduction fragment')
for key in disabled:
    subprocess.run([str(kernel / 'scripts/config'), '--file', str(out / '.config'), '--disable', key], check=True)
for key in re.findall(r'^CONFIG_(\w+)=y$', fragment_text, re.M):
    subprocess.run([str(kernel / 'scripts/config'), '--file', str(out / '.config'), '--enable', key], check=True)
env = {**os.environ, 'Q3_OUT': str(out), 'Q3_LOCALVERSION': '-gd7102a837402-q3-' + args.profile}
with (out / 'configure.log').open('w') as log:
    subprocess.run(['bash', str(repo / 'tools/q3make'), 'HOSTCFLAGS=-DOPENSSL_NO_ENGINE', 'olddefconfig'],
                   env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
def settings(path):
    result = {}
    for line in path.read_text().splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
            result[key] = value
    return result
before, after = settings(base), settings(out / '.config')
for key in disabled:
    if 'CONFIG_' + key in after:
        raise SystemExit('Requested disabled subsystem was re-enabled: ' + key)
required = set(re.findall(r'^CONFIG_(\w+)=y$', (repo / 'quest3/ram-first-candidate/usb-builtin.fragment').read_text(), re.M))
required.update(('MSM_QMP', 'QCOM_AOSS_QMP', 'CFI_CLANG', 'CFI_CLANG_SHADOW',
                 'SHADOW_CALL_STACK', 'LTO_CLANG_FULL', 'MODVERSIONS',
                 'USB_GADGET', 'USB_DWC3', 'USB_CONFIGFS', 'USB_CONFIGFS_ECM',
                 'USB_LIBCOMPOSITE', 'USB_F_ECM', 'USB_U_ETHER', 'NET', 'INET',
                 'PROC_FS', 'SYSFS', 'TMPFS', 'CONFIGFS_FS', 'UNIX98_PTYS',
                 'PSTORE', 'PSTORE_RAM', 'PSTORE_CONSOLE', 'PSTORE_PMSG',
                 'DMADEVICES', 'DMA_ENGINE', 'DMA_VIRTUAL_CHANNELS',
                 'BLK_DEV_INITRD', 'RD_GZIP', 'BINFMT_ELF', 'BINFMT_SCRIPT',
                  'TTY', 'UNIX'))
if args.profile == 'usb-trim3':
    required.update(('KALLSYMS', 'DEBUG_INFO', 'DEBUG_INFO_DWARF4', 'FRAME_POINTER'))
for key in sorted(required):
    if after.get('CONFIG_' + key) != 'y':
        raise SystemExit('Required builtin/protection lost: ' + key)
hardening = ('SECURITY', 'SECURITY_SELINUX', 'SECCOMP', 'SECCOMP_FILTER',
             'HARDENED_USERCOPY', 'STACKPROTECTOR_STRONG', 'STRICT_KERNEL_RWX',
             'STRICT_MODULE_RWX', 'RANDOMIZE_BASE')
for key in hardening:
    if before.get('CONFIG_' + key) != after.get('CONFIG_' + key):
        raise SystemExit('Baseline hardening changed: ' + key)
diff = subprocess.check_output([str(kernel / 'scripts/diffconfig'), str(base), str(out / '.config')], text=True)
(out / 'reduction.diff').write_text(diff)
report = {'profile': 'q3-' + args.profile, 'source_revision': revision,
          'baseline_config_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
          'config_sha256': hashlib.sha256((out / '.config').read_bytes()).hexdigest(),
          'disabled_roots': disabled, 'required_builtins_preserved': sorted(required),
          'checked_hardening_unchanged': list(hardening), 'diff_lines': len(diff.splitlines()),
          'source_host_patch_not_a_target_driver_patch': True,
          'kernel_compiled': False, 'image_size_measured': False,
          'dependency_closure_hardware_validated': False, 'boot_ready': False}
(out / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
