#!/usr/bin/env python3
"""Reproducible offline budget/order comparison; no direct writer or providers."""
import importlib.util
from pathlib import Path

import staging_comparison as c
import relocation_plan as s
import returned_layout as r

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('relocation_cases',here/'test-relocation-plan.py')
cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)


def denied(function,*args,**kwargs):
    try: function(*args,**kwargs)
    except ValueError: pass
    else: raise AssertionError('invalid comparison assumptions/input accepted')


def comparison(data,**kwargs):
    report=c.compare(*data[:4],attempt=cases.cases.ATTEMPT,**kwargs)
    for field in (*s.flags(),'direct_writer_implemented','direct_writer_authorized','streaming_io_implemented',
                  'cpu_mapping_verified','cache_protocol_verified','target_readback_verified',
                  'source_io_availability_verified','rollback_safety_verified',
                  'runtime_peak_memory_measured','route_selected_for_runtime'):
        assert report[field] is False
    assert report['image_request_reduction_bytes']==0 and report['destinations_identical_for_both']
    assert not report['assumptions']['direct_no_copy_transition_implemented']
    assert not report['assumptions']['transition_budget_validated_for_direct']
    assert not report['assumptions']['page_cache_stacks_rejected_pages_and_other_kernel_costs_included']
    return report


data=cases.large_data;model=s.summary(cases.large)
report=comparison(data)
reloc=report['relocation'];direct=report['direct_streaming_hypothesis']
assert reloc['accounted_destination_plus_work_bytes']==model['modeled_retained_bytes']==71962624
assert reloc['retained_source_bytes']==model['source_staging_bytes']==34066432
assert reloc['descriptor_pages']==model['descriptor_pages']==33
assert direct['destination_requested_bytes']==reloc['destination_requested_bytes']==36*r.MIB
assert direct['accounted_work_bytes']==4*r.PAGE
assert direct['accounted_destination_plus_work_bytes']==37765120  # 36.015625 MiB, only under explicit assumptions.
assert report['accounted_retained_bytes_saved_by_direct']==34197504  # 32.61328125 MiB, NOT measured RSS reduction.
assert report['image_request_bytes']==32*r.MIB
assert direct['retained_source_bytes']==direct['descriptor_bytes']==direct['late_relocation_copy_pages_assumed']==0
assert reloc['late_relocation_copy_pages_assumed']==8317
assert direct['logical_destination_stage_bytes']==reloc['logical_destination_stage_bytes']==34066432
assert direct['logical_zero_fill_bytes']==reloc['logical_zero_fill_bytes']
assert direct['logical_file_bytes']+direct['logical_zero_fill_bytes']==direct['logical_destination_stage_bytes']
assert report['accounted_memory_preference']=='direct-streaming-memory-favorable-hypothesis-only'
assert 'all-destination-and-work-handles-owned-and-retained' in report['required_common_gates']
assert 'no-external-writer-or-stale-dma-alias-into-those-ranges' in report['required_direct_first_write_gates']
assert 'source-equals-destination-descriptors' in report['forbidden_unreviewed_shortcuts']
assert 'null-first-desc-through-the-current-loader-virt-to-phys-path' in report['forbidden_unreviewed_shortcuts']
assert report['order_review']['after_irreversible_shutdown']=='neither-route-provides-normal-rollback-or-automatic-retry'

for bounce in (r.PAGE,64*1024,2*r.MIB):
    alternative=comparison(data,bounce_bytes=bounce)
    assert alternative['direct_streaming_hypothesis']['accounted_work_bytes']==bounce+3*r.PAGE
    assert alternative['relocation']==reloc
    assert alternative['accounted_retained_bytes_saved_by_direct']==reloc['accounted_work_bytes']-bounce-3*r.PAGE
scratch=comparison(data,scratch_pages=4)
assert scratch['relocation']['accounted_work_bytes']==reloc['accounted_work_bytes']+4*r.PAGE
assert scratch['direct_streaming_hypothesis']['accounted_work_bytes']==direct['accounted_work_bytes']+4*r.PAGE
assert scratch['accounted_retained_bytes_saved_by_direct']==report['accounted_retained_bytes_saved_by_direct']

# Direct is not universally smaller: a large assumed stream buffer can outweigh
# the source/descriptors of tiny inputs. Do not hard-code a runtime winner.
small=cases.fixture(k=cases.cases.image(size=r.PAGE))
less=comparison(small,bounce_bytes=2*r.MIB)
assert less['accounted_retained_bytes_saved_by_direct']<0
assert less['accounted_memory_preference']=='relocation-accounting-smaller-for-this-stream-budget-only'
equal=comparison(small,bounce_bytes=4*r.PAGE)
assert equal['accounted_retained_bytes_saved_by_direct']==0
assert equal['accounted_memory_preference']=='equal-accounting-no-runtime-preference'

for bounce in (0,True,r.PAGE-1,r.PAGE+1,2*r.MIB+r.PAGE,-r.PAGE,'4096'):
    denied(comparison,data,bounce_bytes=bounce)
for scratch in (-1,True,s.MAX_SCRATCH+1,'0'):
    denied(comparison,data,scratch_pages=scratch)
bad=list(data[:4]);bad[2]=cases.cases.dtb()
denied(c.compare,*bad,attempt=cases.cases.ATTEMPT)
denied(c.compare,*data[:4],attempt='b'*32)
bad=list(data[:4]);bad[3]=bad[3][:2]
denied(c.compare,*bad,attempt=cases.cases.ATTEMPT)

source=Path(c.__file__).read_text()
for forbidden in ('import os','import socket','import subprocess','open(', 'exec(', 'eval(',
                  'def write','def execute','def acquire','def release','import controller'):
    assert forbidden not in source
print('PASS offline staging comparison: same destinations/zero-fill, relocation cross-check, bounded-stream what-if budget, scratch parity, tiny-input reversal and no write/ownership/cache/rollback/runtime claim')
