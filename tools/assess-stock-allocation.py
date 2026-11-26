#!/usr/bin/env python3
"""Offline allocation-route geometry/API review; never calls an allocator or selects a base."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

MIB = 1024 * 1024
PAGE = 4096
ALIGN = 2 * MIB
ANCILLARY_SLOT = 2 * MIB
REQUIRED_EXPORTS = ('dma_contiguous_default_area', 'cma_get_name', 'cma_alloc',
                    'cma_release', 'of_reserved_mem_lookup', 'of_find_node_opts_by_path',
                    'alloc_pages_exact', 'free_pages_exact')


def assess(image, initrd, dtb, descriptors, config, symvers):
    if len(image) < 64 or image[56:60] != b'ARM\x64':
        raise ValueError('not a raw ARM64 Image')
    offset, size, flags = struct.unpack_from('<QQQ', image, 8)
    if offset != 0 or not size or size < len(image) or flags & 1 or flags & 6 not in (0,2) or not flags & 8:
        raise ValueError('unsupported Image header')
    if not 0 < len(initrd) <= ANCILLARY_SLOT:
        raise ValueError('initrd outside reviewed separate-slot capacity')
    if not 40 <= len(dtb) <= ANCILLARY_SLOT or dtb[:4] != b'\xd0\x0d\xfe\xed' or struct.unpack_from('>I',dtb,4)[0] != len(dtb):
        raise ValueError('invalid DTB header/size for capacity review')
    if descriptors.get('status') != '13-runtime-descriptor-locations-confirmed' or descriptors.get('descriptor_count') != 13:
        raise ValueError('reviewed descriptor evidence required')
    regions = descriptors.get('regions',[])
    if (len(regions) != 13 or len({r.get('node') for r in regions}) != 13 or
            not all(r.get('descriptor_consistent') for r in regions) or
            descriptors.get('same_boot_as_input_maps') is not True):
        raise ValueError('complete matching descriptor evidence required')
    defaults = [r for r in regions if r.get('node') == '/reserved-memory/linux,cma']
    if len(defaults) != 1 or not defaults[0].get('descriptor_consistent'):
        raise ValueError('default-pool descriptor evidence missing')
    capacity = defaults[0].get('size_bytes')
    if capacity != 32 * MIB:
        raise ValueError('pool capacity differs from reviewed 32MiB evidence')
    settings = set(config.splitlines())
    for symbol in ('ARM64_4K_PAGES','DMA_CMA','CMA'):
        if 'CONFIG_'+symbol+'=y' not in settings:
            raise ValueError('unsupported stock configuration: '+symbol)
    match = re.search(r'(?m)^CONFIG_FORCE_MAX_ZONEORDER=(\d+)$',config)
    if not match or int(match[1]) != 11:
        raise ValueError('unreviewed buddy MAX_ORDER')
    max_order = int(match[1])
    exported = {fields[1] for line in symvers.splitlines() if len(fields:=line.split()) >= 4}
    missing = sorted(set(REQUIRED_EXPORTS)-exported)
    image_slot = (size+ALIGN-1)//ALIGN*ALIGN
    order = ((ANCILLARY_SLOT+PAGE-1)//PAGE-1).bit_length()
    combined = image_slot+2*ANCILLARY_SLOT
    return {
        'scope':'offline route assessment, not a runtime pool identity or ownership check',
        'image_file_bytes':len(image), 'required_image_bytes':size,
        'image_slot_bytes':image_slot, 'image_alignment_bytes':ALIGN,
        'observed_default_pool_capacity_bytes':capacity,
        'max_buddy_single_allocation_bytes':PAGE*(1<<(max_order-1)),
        'required_exports_present':not missing, 'missing_exports':missing,
        'combined_route':{'required_contiguous_bytes':combined,
                          'fits_observed_default_pool':combined <= capacity,
                          'max_image_bytes_with_two_2mib_slots':capacity-2*ANCILLARY_SLOT},
        'separate_route':{'image_provider':'default CMA via typed API; identity must be checked at runtime',
                          'image_request_bytes':image_slot,
                          'image_fits_observed_default_pool':image_slot <= capacity,
                          'max_image_bytes':capacity,
                          'image_reduction_to_capacity_bytes':max(0,size-capacity),
                          'initrd_provider':'buddy allocation, reviewed low-memory policy required',
                          'initrd_payload_bytes':len(initrd),'initrd_request_bytes':ANCILLARY_SLOT,
                          'dtb_provider':'buddy allocation, reviewed low-memory policy required',
                          'dtb_payload_bytes':len(dtb),'dtb_request_bytes':ANCILLARY_SLOT,
                          'ancillary_buddy_order':order,'ancillary_order_supported':order < max_order,
                          'total_requested_bytes':image_slot+2*ANCILLARY_SLOT,
                          'single_contiguous_all_payload_window_required':False},
        'default_cma_runtime_identity_verified':False,
        'default_pool_available_capacity_proven':False,
        'pool_lifetime_contract_validated_on_stock_binary':False,
        'dedicated_pool_borrowing_allowed':False,
        'raw_alloc_contig_range_on_cma_allowed':False,
        'physical_placement_protocol_checked':False,
        'allocator_call_authorized':False, 'allocator_called':False,
        'new_physical_base_selected':False,'ownership_acquired':False,
        'dma_safety_proven':False,'allocation_experiment_ready':False,'boot_ready':False,
        'note':'Capacity is from one captured public reserved-memory descriptor, not free space '
               'or independently verified dma_contiguous_default_area identity. The separate '
               'layout still requires ownership of every allocation, non-overlap, Image/DT '
               'alignment, the ARM64 initrd window, DT updates and complete handoff/DMA review. '
               'No pool-private fields, current PFNs or device state are read.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('image','initrd','dtb','descriptors','config','symvers'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    try:
        data = {name:getattr(args,name).read_bytes() for name in ('image','initrd','dtb','descriptors','config','symvers')}
        result = assess(data['image'],data['initrd'],data['dtb'],json.loads(data['descriptors']),data['config'].decode(),data['symvers'].decode())
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        parser.exit(2,str(error)+'\n')
    result['input_sha256'] = {name:hashlib.sha256(blob).hexdigest() for name,blob in data.items()}
    print(json.dumps(result,indent=2))
