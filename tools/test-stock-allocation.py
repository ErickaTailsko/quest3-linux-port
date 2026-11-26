#!/usr/bin/env python3
"""Synthetic allocator capacity/API decisions; never requests kernel memory."""
import importlib.util
from pathlib import Path
import struct

spec=importlib.util.spec_from_file_location('allocation',Path(__file__).with_name('assess-stock-allocation.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def image(size):
    data=bytearray(64);data[56:60]=b'ARM\x64';struct.pack_into('<QQQ',data,8,0,size,10);return data
dtb=bytearray(40);struct.pack_into('>II',dtb,0,0xd00dfeed,40)
descriptors={'status':'13-runtime-descriptor-locations-confirmed','descriptor_count':13,
             'same_boot_as_input_maps':True,
             'regions':[{'node':'/reserved-memory/linux,cma','descriptor_consistent':True,'size_bytes':32*m.MIB}]+
                       [{'node':'/reserved-memory/unit-'+str(i),'descriptor_consistent':True} for i in range(12)]}
config='CONFIG_ARM64_4K_PAGES=y\nCONFIG_DMA_CMA=y\nCONFIG_CMA=y\nCONFIG_FORCE_MAX_ZONEORDER=11\n'
symvers=''.join('0x00000000\t'+name+'\tvmlinux\tEXPORT_SYMBOL_GPL\n' for name in m.REQUIRED_EXPORTS)
def assess(size, table=symvers):return m.assess(image(size),b'initrd',dtb,descriptors,config,table)
r=assess(37683200)
assert r['combined_route']['required_contiguous_bytes']==40*m.MIB
assert r['separate_route']['image_request_bytes']==36*m.MIB
assert r['separate_route']['image_reduction_to_capacity_bytes']==4128768
assert not r['separate_route']['image_fits_observed_default_pool']
trim3 = assess(32768000)
assert trim3['separate_route']['image_fits_observed_default_pool']
assert trim3['separate_route']['image_request_bytes'] == 32*m.MIB
assert trim3['observed_default_pool_capacity_bytes']-trim3['required_image_bytes'] == 786432
assert trim3['observed_default_pool_capacity_bytes']-trim3['separate_route']['image_request_bytes'] == 0
assert trim3['separate_route']['total_requested_bytes'] == 36*m.MIB
assert not trim3['combined_route']['fits_observed_default_pool']
assert not trim3['allocation_experiment_ready'] and not trim3['ownership_acquired']
assert r['max_buddy_single_allocation_bytes']==4*m.MIB
assert r['separate_route']['ancillary_buddy_order']==9
assert assess(32*m.MIB)['separate_route']['image_fits_observed_default_pool']
assert not assess(32*m.MIB)['combined_route']['fits_observed_default_pool']
assert assess(28*m.MIB)['combined_route']['fits_observed_default_pool']
assert assess(32*m.MIB+1)['separate_route']['image_request_bytes']==34*m.MIB
assert not assess(28*m.MIB,'')['required_exports_present']
for key in ['default_cma_runtime_identity_verified','default_pool_available_capacity_proven',
            'dedicated_pool_borrowing_allowed','raw_alloc_contig_range_on_cma_allowed',
            'allocator_call_authorized','allocator_called','new_physical_base_selected',
            'ownership_acquired','allocation_experiment_ready','boot_ready']:
    assert r[key] is False
for bad_image,bad_initrd,bad_dtb,bad_config in [(image(0),b'i',dtb,config),
        (image(32*m.MIB),b'',dtb,config),(image(32*m.MIB),b'i',b'bad',config),
        (image(32*m.MIB),b'i',dtb,config.replace('=11','=12'))]:
    try:m.assess(bad_image,bad_initrd,bad_dtb,descriptors,bad_config,symvers)
    except ValueError:pass
    else:raise AssertionError('unsupported evidence accepted')
print('PASS stock route capacity: current Image rejected, 32MiB split vs 28MiB combined, buddy orders, rounding/API guards and no allocation/ownership permission')
