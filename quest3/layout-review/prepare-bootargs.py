from pathlib import Path
import argparse
import hashlib
import json
from fdtcheck import read, rewrite

def prepare(blob):
    nodes, reservations, cpu = read(blob)
    compatible = nodes.get('/', {}).get('compatible', b'').split(b'\0')
    if b'qcom,anorak' not in compatible or b'oculus,eureka' not in compatible:
        raise ValueError('Only the reviewed Quest 3 Eureka/Anorak layout is supported')
    original = nodes['/chosen']['bootargs'].rstrip(b'\0').decode('ascii')
    if '\0' in original or any(char in original for char in ('"', "'", '\\')):
        raise ValueError('Unsupported embedded NUL or quoted bootargs')
    drop = {'rootwait', 'ro', 'rw', 'bootconfig', 'console=none'}
    replace = {'rdinit', 'loglevel', 'log_buf_len', 'panic', 'pstore.compress',
               'root', 'rootfstype', 'rootflags', 'rootdelay', 'rootwait', 'init',
               'msm_drm.dsi_display0', 'qcom_dload_mode.download_mode',
               'qcom_dload_mode.dump_mode', 'qcom_dload_mode.emmc_dload'}
    kept = [x for x in original.split() if x not in drop and x.split('=', 1)[0] not in replace]
    args = ' '.join(kept + ['rdinit=/init', 'loglevel=7', 'log_buf_len=1M', 'panic=0', 'pstore.compress=none'])
    target = rewrite(blob, {('/chosen', 'bootargs'): args.encode() + b'\0'})
    after, reservations2, cpu2 = read(target)
    expected = {path: dict(props) for path, props in nodes.items()}
    expected['/chosen']['bootargs'] = args.encode() + b'\0'
    if after != expected or reservations2 != reservations or cpu2 != cpu:
        raise ValueError('Unexpected DT modification')
    return target, args

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepare a host-only RAM-first diagnostic DT copy; never deploys or boots it.')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.input, args.out
    if output.exists() or source.resolve() == output.resolve():
        parser.error('Output must be a new file distinct from input')
    target, args = prepare(source.read_bytes())
    with output.open('xb') as f:
        f.write(target)
    print(json.dumps({'output_sha256': hashlib.sha256(target).hexdigest(),
                      'bootargs': args, 'only_chosen_bootargs_changed': True,
                      'disk_root_arguments_removed': True,
                      'device_modified': False, 'boot_tested': False}, indent=2))
