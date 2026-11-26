#!/usr/bin/env python3
"""Synthetic verifier regressions only, not a kernel build or a boot test."""
import importlib.util
from pathlib import Path
import struct
import tempfile

spec = importlib.util.spec_from_file_location('candidate', Path(__file__).with_name('verify-qmp-candidate.py'))
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
with tempfile.TemporaryDirectory(prefix='qmp-artifacts-') as temporary:
    root = Path(temporary)
    files = {
        '.config': ''.join('CONFIG_' + key + '=y\n' for key in candidate.REQUIRED).encode(),
        'include/config/kernel.release': b'5.10.246-gd7102a837402-q3-ram-first-qmp\n',
        'modules.builtin': ''.join('kernel/' + driver + '.ko\n' for driver in candidate.DRIVERS).encode(),
        'System.map': b'1 T qmp_get\n2 T qmp_send\n3 d qmp_mbox_driver\n',
        'Module.symvers': b'0x12345678 qmp_send vmlinux EXPORT_SYMBOL\n',
    }
    elf = bytearray(64)
    elf[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', elf, 18, 183)
    files['vmlinux'] = bytes(elf)  # Header fixture only, not a runnable ELF.
    image = bytearray(4096)
    image[56:60] = b'ARM\x64'
    struct.pack_into('<QQQ', image, 8, 0, 4096, 0xa)
    files['arch/arm64/boot/Image'] = bytes(image)
    for driver in candidate.DRIVERS:
        path = Path(driver)
        files[str(path.parent / ('.' + path.name + '.o.cmd'))] = b'clang -flto -fsanitize=cfi -fsanitize=shadow-call-stack -ffixed-x18\n'
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    report = candidate.verify(root)
    assert report['artifact_checks_passed']
    assert not report['boot_ready'] and not report['boot_tested']
    assert not report['inherited_qmp_handshake_validated'] and not report['destination_ram_owned']
    for name, bad in [('.config', files['.config'].replace(b'CONFIG_MSM_QMP=y', b'CONFIG_MSM_QMP=m')),
                      ('.config', files['.config'].replace(b'CONFIG_CFI_CLANG=y', b'# CONFIG_CFI_CLANG is not set')),
                      ('.config', files['.config'].replace(b'CONFIG_QCOM_IPCC=y', b'# CONFIG_QCOM_IPCC is not set')),
                      ('.config', files['.config'].replace(b'CONFIG_BINFMT_SCRIPT=y', b'# CONFIG_BINFMT_SCRIPT is not set')),
                      ('.config', files['.config'].replace(b'CONFIG_RD_GZIP=y', b'# CONFIG_RD_GZIP is not set')),
                      ('.config', files['.config'] + b'CONFIG_CFI_PERMISSIVE=y\n'),
                      ('modules.builtin', b''), ('System.map', b''), ('Module.symvers', b''),
                      ('vmlinux', b''), ('include/config/kernel.release', b'wrong\n'),
                      ('arch/arm64/boot/Image', b'bad image'),
                      ('drivers/mailbox/.msm_qmp.o.cmd', b'clang -flto\n')]:
        path = root / name
        path.write_bytes(bad)
        try:
            candidate.verify(root)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid artifact accepted: ' + name)
        path.write_bytes(files[name])
    for offset, size, flags in [(0x80000, 4096, 0xa), (0, 0x3000001, 0xa),
                                (0, 4095, 0xa), (0, 4096, 0xb), (0, 4096, 0x2)]:
        bad = bytearray(image)
        struct.pack_into('<QQQ', bad, 8, offset, size, flags)
        (root / 'arch/arm64/boot/Image').write_bytes(bad)
        try:
            candidate.verify(root)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid Image header accepted')
    (root / 'arch/arm64/boot/Image').write_bytes(files['arch/arm64/boot/Image'])
    (root / 'include/config/kernel.release').write_text('5.10.246-gd7102a837402-q3-usb-trim1\n')
    (root / '.config').write_bytes(files['.config'] + b'CONFIG_DMADEVICES=y\nCONFIG_DMA_ENGINE=y\nCONFIG_DMA_VIRTUAL_CHANNELS=y\n')
    (root / 'vmlinux.symvers').write_bytes(files['Module.symvers'])
    report = candidate.verify(root, 'usb-trim1', True)
    assert report['image_only_build'] and report['checked_export_table'] == 'vmlinux.symvers'
    (root / '.config').write_bytes((root / '.config').read_bytes() + b'CONFIG_DRM=y\n')
    try:
        candidate.verify(root, 'usb-trim1', True)
    except ValueError:
        pass
    else:
        raise AssertionError('trim profile accepted enabled DRM')
    (root / '.config').write_bytes((root / '.config').read_bytes().replace(b'CONFIG_DRM=y\n', b''))
    (root / 'include/config/kernel.release').write_text('5.10.246-gd7102a837402-q3-usb-trim2\n')
    assert candidate.verify(root, 'usb-trim2', True)['profile'] == 'usb-trim2'
    (root / '.config').write_bytes((root / '.config').read_bytes() + b'CONFIG_EXT4_FS=y\n')
    try:
        candidate.verify(root, 'usb-trim2', True)
    except ValueError:
        pass
    else:
        raise AssertionError('trim2 accepted enabled disk filesystem')
    (root / '.config').write_bytes(files['.config'] + b'CONFIG_DMADEVICES=y\nCONFIG_DMA_ENGINE=y\nCONFIG_DMA_VIRTUAL_CHANNELS=y\n' +
                                  ''.join('CONFIG_'+key+'=y\n' for key in candidate.TRIM3_REQUIRED).encode())
    (root / 'include/config/kernel.release').write_text('5.10.246-gd7102a837402-q3-usb-trim3\n')
    assert candidate.verify(root, 'usb-trim3', True)['reviewed_image_size_limit_bytes'] == 32*1024*1024
    assert candidate.verify(root, 'usb-trim3', True)['image_entry_is_legacy_layout_reference_not_selected_destination']
    command_path = root / 'drivers/mailbox/.msm_qmp.o.cmd'
    original_command = command_path.read_bytes()
    command_path.write_bytes(original_command.replace(b'-flto ',b'-flto=thin '))
    try:candidate.verify(root,'usb-trim3',True)
    except ValueError:pass
    else:raise AssertionError('trim3 accepted provider ThinLTO')
    command_path.write_bytes(original_command)
    (root / 'System.map').write_bytes(files['System.map'] + b'4 R __start_BTF\n')
    try:candidate.verify(root,'usb-trim3',True)
    except ValueError:pass
    else:raise AssertionError('trim3 accepted linked embedded BTF')
    (root / 'System.map').write_bytes(files['System.map'])
    for key in ('DEBUG_INFO_BTF', 'KALLSYMS_ALL', 'KUNIT'):
        config = (root / '.config').read_bytes()
        (root / '.config').write_bytes(config + ('CONFIG_'+key+'=y\n').encode())
        try:candidate.verify(root, 'usb-trim3', True)
        except ValueError:pass
        else:raise AssertionError('trim3 accepted reactivated diagnostic root: '+key)
        (root / '.config').write_bytes(config)
    for key in ('KALLSYMS','DEBUG_INFO_DWARF4','HARDENED_USERCOPY','PSTORE_PMSG'):
        config = (root / '.config').read_bytes()
        (root / '.config').write_bytes(config.replace(('CONFIG_'+key+'=y\n').encode(),b''))
        try:candidate.verify(root, 'usb-trim3', True)
        except ValueError:pass
        else:raise AssertionError('trim3 accepted missing diagnostic/protection: '+key)
        (root / '.config').write_bytes(config)
    for size in [32*1024*1024,32*1024*1024+1]:
        test_image = bytearray(image)
        struct.pack_into('<Q',test_image,16,size)
        (root / 'arch/arm64/boot/Image').write_bytes(test_image)
        if size == 32*1024*1024:
            candidate.verify(root,'usb-trim3',True)
        else:
            try:candidate.verify(root,'usb-trim3',True)
            except ValueError:pass
            else:raise AssertionError('trim3 accepted Image beyond 32MiB')
print('PASS QMP artifact verifier: required built-ins/protections, release, image bounds/flags, linked symbols and missing artifacts; no boot claim')
