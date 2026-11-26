#!/usr/bin/env python3
"""Offline WHAT-IF accounting/order comparison, NOT a direct RAM writer.

No allocator, streaming reader, target writes, provider callbacks or handoff.
Input bytes live in host memory; budgets describe hypothetical target resources,
not this Python process or a measured stock-kernel peak.
"""
import returned_layout as r
from relocation_plan import DESCRIPTOR_CAPACITY,MAX_SCRATCH,flags

PROFILE='q3-staging-comparison-host-v1'
TRANSITION_PAGES_ASSUMED=3  # code + PGD + PUD, held equal; no-copy stub NOT validated.

COMMON_REQUIRED_GATES=(
    'new-specific-authorization-for-allocation-and-write-scope',
    'current-boot-identity-and-immutable-payload-handles',
    'default-cma-pointer-identity-typed-abi-lifetime-and-capacity',
    'all-destination-and-work-handles-owned-and-retained',
    'valid-pfns-cpu-mappings-and-complete-range-alias-review',
    'dt-ram-reservations-chosen-and-image-initrd-window',
    'recoverable-logs-and-fail-closed-journal-transport',
    'global-cpu-dma-smmu-watchdog-qmp-shutdown-review',
    'cache-poc-icache-mmu-registers-and-cfi-compatible-entry',
)
DIRECT_FIRST_WRITE_GATES=(
    'explicit-authorization-to-write-the-actually-owned-destinations',
    'writable-cpu-mapping-with-reviewed-attributes-for-every-target-byte',
    'no-external-writer-or-stale-dma-alias-into-those-ranges',
    'bounded-owned-stream-buffer-and-reviewed-read-completion',
    'source-io-available-before-irreversible-shutdown',
    'complete-file-read-and-zero-fill-validation-before-shutdown',
    'target-content-stability-until-handoff-and-reviewed-readback',
    'clean-destination-data-to-poc-after-last-write-not-only-source-buffers',
    'dedicated-reviewed-no-copy-transition-not-self-copy-descriptors',
)


def compare(image,initrd,prepared_dtb,allocations,*,attempt,bounce_bytes=r.PAGE,scratch_pages=0):
    """Compare like-for-like destinations under EXPLICIT unimplemented assumptions.

    The direct hypothesis streams into exclusive, actually acquired destinations
    with a bounded page-aligned buffer. Nothing here verifies those conditions or
    grants ownership/write permission. Relocation is also not allowed to target
    unowned RAM, even if its writes occur after shutdown.
    """
    if type(bounce_bytes) is not int or not r.PAGE<=bounce_bytes<=r.ALIGN or bounce_bytes%r.PAGE:
        raise ValueError('explicit page-aligned 4KiB..2MiB stream budget required')
    if type(scratch_pages) is not int or not 0<=scratch_pages<=MAX_SCRATCH:
        raise ValueError('bounded same-for-both scratch-page budget required')
    layout=r.plan(image,initrd,prepared_dtb,allocations,attempt=attempt)
    if not layout['chosen_initrd_matches']: raise ValueError('DT chosen must be prepared for supplied addresses')
    destination=layout['total_request_bytes']
    source_pages=sum(slot['copy_pages'] for slot in layout['slots'])
    staging_bytes=source_pages*r.PAGE
    file_bytes=sum(slot['file_bytes'] for slot in layout['slots'])
    descriptors=(source_pages+DESCRIPTOR_CAPACITY-1)//DESCRIPTOR_CAPACITY
    descriptor_bytes=descriptors*r.PAGE
    transition_bytes=TRANSITION_PAGES_ASSUMED*r.PAGE
    scratch_bytes=scratch_pages*r.PAGE
    relocation_work=staging_bytes+descriptor_bytes+transition_bytes+scratch_bytes
    direct_work=bounce_bytes+transition_bytes+scratch_bytes
    savings=relocation_work-direct_work
    if savings>0: preference='direct-streaming-memory-favorable-hypothesis-only'
    elif savings==0: preference='equal-accounting-no-runtime-preference'
    else: preference='relocation-accounting-smaller-for-this-stream-budget-only'
    def route(work,retained_sources,descriptor_pages,buffer,late_copy_pages):
        return dict(destination_requested_bytes=destination,retained_source_bytes=retained_sources,
            descriptor_pages=descriptor_pages,descriptor_bytes=descriptor_pages*r.PAGE,
            stream_buffer_budget_bytes=buffer,transition_pages_assumed=TRANSITION_PAGES_ASSUMED,
            transition_bytes_assumed=transition_bytes,scratch_pages_assumed=scratch_pages,
            scratch_bytes_assumed=scratch_bytes,accounted_work_bytes=work,
            accounted_destination_plus_work_bytes=destination+work,
            logical_destination_stage_bytes=staging_bytes,logical_file_bytes=file_bytes,
            logical_zero_fill_bytes=staging_bytes-file_bytes,
            late_relocation_copy_pages_assumed=late_copy_pages)
    return dict(profile=PROFILE,scope='offline conditional accounting, NOT a runtime peak or a staging implementation',
        attempt=attempt,input_sha256=layout['input_sha256'],
        copy_pages_by_role={slot['role']:slot['copy_pages'] for slot in layout['slots']},
        image_request_bytes=layout['slots'][0]['allocation_bytes'],
        image_request_reduction_bytes=0,destinations_identical_for_both=True,
        relocation=route(relocation_work,staging_bytes,descriptors,0,source_pages),
        direct_streaming_hypothesis=route(direct_work,0,0,bounce_bytes,0),
        accounted_retained_bytes_saved_by_direct=savings,
        accounted_memory_preference=preference,
        assumptions=dict(same_transition_and_scratch_budget_for_both=True,
            direct_inputs_streamed_not_materialized_as_full_extra_buffers=True,
            direct_no_copy_transition_implemented=False,
            stream_buffer_allocator_rounding_verified=False,
            transition_budget_validated_for_direct=False,
            page_cache_stacks_rejected_pages_and_other_kernel_costs_included=False,
            python_process_memory_is_the_target_budget=False),
        order_review=dict(
            relocation_before_irreversible_shutdown=[
                'acquire-destinations-and-all-owned-source-descriptor-transition-pages',
                'read-validate-source-snapshots-zero-fill-and-descriptors',
                'finish-fallible-io-and-retain-all-handles'],
            relocation_final_phase=[
                'complete-reviewed-global-shutdown-and-cache-preparation',
                'copy-sources-to-owned-destinations-through-validated-physical-path',
                'enter-new-kernel-with-reviewed-architectural-state'],
            direct_before_irreversible_shutdown=[
                'acquire-destinations-stream-buffer-and-transition-work',
                'prove-destination-mappings-and-writer-dma-exclusion-before-first-write',
                'stream-complete-files-and-zero-fill-into-exclusive-owned-destinations',
                'validate-target-content-finish-io-and-prevent-further-mutation'],
            direct_final_phase=[
                'complete-reviewed-global-shutdown',
                'clean-destinations-and-transition-state-to-poc-with-correct-attributes',
                'use-reviewed-no-copy-entry-path'],
            partial_read_before_shutdown=dict(
                relocation='source-buffers-partial-destinations-not-yet-written',
                direct='owned-destinations-may-be-partially-written',
                cleanup='conditional-on-real-handles-no-inflight-access-and-separate-review-never-automatic'),
            after_irreversible_shutdown='neither-route-provides-normal-rollback-or-automatic-retry'),
        required_common_gates=list(COMMON_REQUIRED_GATES),
        required_direct_first_write_gates=list(DIRECT_FIRST_WRITE_GATES),
        forbidden_unreviewed_shortcuts=[
            'source-equals-destination-descriptors',
            'null-first-desc-through-the-current-loader-virt-to-phys-path',
            'source-only-cache-flush-for-a-direct-written-destination',
            'late-file-io-after-storage-or-cpu-shutdown',
            'automatic-fallback-to-another-route-after-unknown-completion'],
        implementation_note='existing loader stays fixed-address/disarmed; direct writer and adapter do not exist',
        direct_writer_implemented=False,direct_writer_authorized=False,
        streaming_io_implemented=False,cpu_mapping_verified=False,cache_protocol_verified=False,
        target_readback_verified=False,source_io_availability_verified=False,
        rollback_safety_verified=False,runtime_peak_memory_measured=False,
        route_selected_for_runtime=False,**flags())
