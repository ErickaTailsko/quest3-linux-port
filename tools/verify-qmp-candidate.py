#!/usr/bin/env python3
"""Offline artifact checks for the separate QMP candidate; never proves boot."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

REQUIRED = ('MSM_QMP', 'QCOM_AOSS_QMP', 'CFI_CLANG', 'CFI_CLANG_SHADOW',
            'SHADOW_CALL_STACK', 'LTO_CLANG_FULL', 'MODVERSIONS',
            'MAILBOX', 'COMMON_CLK', 'PM', 'QCOM_IPCC', 'ARM_GIC_V3',
            'BLK_DEV_INITRD', 'RD_GZIP', 'BINFMT_ELF', 'BINFMT_SCRIPT',
            'TTY', 'UNIX98_PTYS', 'DEVTMPFS', 'TMPFS', 'PROC_FS', 'SYSFS',
            'CONFIGFS_FS', 'UNIX', 'INET', 'USB_CONFIGFS_ECM')
DRIVERS = ('drivers/mailbox/msm_qmp', 'drivers/soc/qcom/qcom_aoss')
TRIM3_REQUIRED = ('KALLSYMS', 'DEBUG_INFO', 'DEBUG_INFO_DWARF4', 'FRAME_POINTER',
                  'SECURITY', 'SECURITY_SELINUX', 'SECCOMP', 'SECCOMP_FILTER',
                  'HARDENED_USERCOPY', 'STACKPROTECTOR_STRONG', 'STRICT_KERNEL_RWX',
                  'STRICT_MODULE_RWX', 'RANDOMIZE_BASE', 'PSTORE', 'PSTORE_RAM',
                  'PSTORE_CONSOLE', 'PSTORE_PMSG')


def verify(out, profile='qmp', image_only=False):
    config = (out / '.config').read_text()
    settings = set(config.splitlines())
    for key in REQUIRED:
        if 'CONFIG_' + key + '=y' not in settings:
            raise ValueError('required built-in/protection missing: ' + key)
    if 'CONFIG_CFI_PERMISSIVE=y' in settings:
        raise ValueError('permissive CFI is not allowed for these candidates')
    release = (out / 'include/config/kernel.release').read_text().strip()
    releases = {'qmp': '5.10.246-gd7102a837402-q3-ram-first-qmp',
                'usb-trim1': '5.10.246-gd7102a837402-q3-usb-trim1',
                'usb-trim2': '5.10.246-gd7102a837402-q3-usb-trim2',
                'usb-trim3': '5.10.246-gd7102a837402-q3-usb-trim3'}
    if profile not in releases or release != releases[profile]:
        raise ValueError('unexpected candidate kernel release')
    if profile in ('usb-trim1', 'usb-trim2', 'usb-trim3'):
        for key in ('MEDIA_SUPPORT', 'DRM', 'HID', 'USB_HID', 'INPUT_JOYSTICK',
                    'NETFILTER', 'IPV6', 'WIRELESS', 'WLAN', 'BT', 'USB_STORAGE'):
            if 'CONFIG_' + key + '=y' in settings or 'CONFIG_' + key + '=m' in settings:
                raise ValueError('trimmed subsystem unexpectedly enabled: ' + key)
        for key in ('DMADEVICES', 'DMA_ENGINE', 'DMA_VIRTUAL_CHANNELS'):
            if 'CONFIG_' + key + '=y' not in settings:
                raise ValueError('shared DMA framework missing: ' + key)
    if profile in ('usb-trim2', 'usb-trim3'):
        for key in ('NET_SCHED', 'BRIDGE', 'L2TP', 'PPP', 'CAN', 'IEEE802154',
                    'VSOCKETS', 'EXT4_FS', 'FUSE_FS', 'OVERLAY_FS', 'VFAT_FS'):
            if 'CONFIG_' + key + '=y' in settings or 'CONFIG_' + key + '=m' in settings:
                raise ValueError('trim2 subsystem unexpectedly enabled: ' + key)
    if profile == 'usb-trim3':
        for key in TRIM3_REQUIRED:
            if 'CONFIG_' + key + '=y' not in settings:
                raise ValueError('trim3 diagnostic/protection missing: ' + key)
        for key in ('DEBUG_INFO_BTF', 'KALLSYMS_ALL', 'KUNIT'):
            if 'CONFIG_' + key + '=y' in settings or 'CONFIG_' + key + '=m' in settings:
                raise ValueError('trim3 diagnostic reduction unexpectedly reverted: ' + key)
    image = (out / 'arch/arm64/boot/Image').read_bytes()
    if len(image) < 64 or image[56:60] != b'ARM\x64':
        raise ValueError('not a raw ARM64 Image')
    offset, size, flags = struct.unpack_from('<QQQ', image, 8)
    limit = 32 * 1024 * 1024 if profile == 'usb-trim3' else 0x3000000
    if offset != 0 or size < len(image) or size > limit:
        raise ValueError('candidate Image does not fit reviewed zero-offset layout')
    if flags & 1 or flags & 6 not in (0, 2) or not flags & 8:
        raise ValueError('unsupported Image architecture flags')
    builtin = set((out / 'modules.builtin').read_text().splitlines())
    for driver in DRIVERS:
        if 'kernel/' + driver + '.ko' not in builtin:
            raise ValueError('driver absent from modules.builtin: ' + driver)
        path = Path(driver)
        command = (out / path.parent / ('.' + path.name + '.o.cmd')).read_text()
        for option in ('-flto', '-fsanitize=cfi', '-fsanitize=shadow-call-stack', '-ffixed-x18'):
            if option not in command:
                raise ValueError('missing compile protection for ' + driver + ': ' + option)
        if profile == 'usb-trim3' and '-flto=thin' in command:
            raise ValueError('trim3 provider compiled with ThinLTO instead of Full LTO')
    symbols = {line.split()[-1] for line in (out / 'System.map').read_text().splitlines() if line.split()}
    for symbol in ('qmp_get', 'qmp_send', 'qmp_mbox_driver'):
        if symbol not in symbols:
            raise ValueError('required linked symbol absent: ' + symbol)
    if profile == 'usb-trim3' and '__start_BTF' in symbols:
        raise ValueError('trim3 unexpectedly links embedded BTF')
    with (out / 'vmlinux').open('rb') as stream:
        elf = stream.read(64)
    if len(elf) < 64 or elf[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', elf, 18)[0] != 183:
        raise ValueError('vmlinux is not an ELF64 little-endian ARM64 artifact')
    export_table = 'vmlinux.symvers' if image_only else 'Module.symvers'
    if not (out / export_table).read_text().strip():
        raise ValueError(export_table + ' unavailable')
    return {
        'artifact_checks_passed': True,
        'kernel_release': release,
        'profile': profile, 'image_only_build': image_only,
        'checked_export_table': export_table,
        'image_bytes': len(image), 'image_size': hex(size),
        'image_entry': '0x90000000',
        'image_entry_is_legacy_layout_reference_not_selected_destination': True,
        'reviewed_image_size_limit_bytes': limit,
        'image_sha256': hashlib.sha256(image).hexdigest(),
        'config_sha256': hashlib.sha256(config.encode()).hexdigest(),
        'qmp_providers_builtin': True,
        'compile_protection_flags_present': True,
        'scope': 'artifact consistency and recorded build flags, not runtime behavior or complete dependency closure',
        'inherited_qmp_handshake_validated': False,
        'destination_ram_owned': False,
        'boot_ready': False, 'boot_tested': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='completed kernel build output directory')
    parser.add_argument('--profile', choices=('qmp', 'usb-trim1', 'usb-trim2', 'usb-trim3'), default='qmp')
    parser.add_argument('--image-only', action='store_true', help='Check vmlinux.symvers, not complete module build exports')
    args = parser.parse_args()
    try:
        report = verify(args.out, args.profile, args.image_only)
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(report, indent=2))
