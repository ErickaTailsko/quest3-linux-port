#!/usr/bin/env python3
"""Abstract lifetime interleavings, not an implementation of kernel locking."""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class State:
    scanner: int = 0
    remover: int = 0
    valid: bool = True
    map_alive: bool = True
    reader: bool = False
    writer: bool = False
    checked: bool = False
    notifier_registered: bool = False
    unsafe: bool = False


def schedules(mode):
    """Preserve each actor's order and prune conflicting acquisitions.

    mem_rwsem holds a reader through use and excludes an exclusive remover.
    cpu_readers lets both actors hold shared CPU-hotplug read locks.
    notifier can veto a future notification, not an earlier approval.
    none is an unprotected validation/use sequence.
    """
    assert mode in {'none', 'cpu_readers', 'mem_rwsem', 'notifier'}
    finished = []

    def visit(state, trace):
        if state.scanner == 4 and state.remover == 4:
            finished.append((state, trace))
            return
        if state.scanner < 4:
            step = state.scanner
            if step != 0 or mode != 'mem_rwsem' or not state.writer:
                new = replace(state, scanner=step+1)
                if step == 0:
                    new = replace(new, reader=mode in {'mem_rwsem', 'cpu_readers'},
                                  notifier_registered=mode == 'notifier')
                elif step == 1:
                    new = replace(new, checked=state.valid)
                elif step == 2:
                    new = replace(new, unsafe=state.checked and not state.map_alive)
                else:
                    new = replace(new, reader=False)
                label = ('enter', 'check', 'use-if-checked', 'leave')[step]
                visit(new, trace+(f'scanner:{label}',))
        if state.remover < 4:
            step = state.remover
            if step != 0 or mode != 'mem_rwsem' or not state.reader:
                if step == 0 and mode == 'notifier' and state.notifier_registered:
                    visit(replace(state, remover=4), trace+('remover:notification-vetoed',))
                else:
                    new = replace(state, remover=step+1)
                    if step == 0:
                        new = replace(new, writer=mode == 'mem_rwsem')
                    elif step == 1:
                        new = replace(new, valid=False)
                    elif step == 2:
                        new = replace(new, map_alive=False)
                    else:
                        new = replace(new, writer=False)
                    label = ('enter-or-notify', 'invalidate', 'free-map', 'leave')[step]
                    visit(new, trace+(f'remover:{label}',))

    visit(State(), ())
    return finished


def witness(mode):
    return next((trace for state, trace in schedules(mode) if state.unsafe), None)


assert witness('none')
assert witness('cpu_readers')
assert witness('notifier')
protected = schedules('mem_rwsem')
assert protected and not any(state.unsafe for state, _ in protected)

# Waiting inside a stopper callback cannot release a paused owner's lock.
paused_owner = {'holds_write_lock': True, 'can_run': False}
callback_can_take_read_lock = not paused_owner['holds_write_lock']
assert not callback_can_take_read_lock and not paused_owner['can_run']

# A snapshot, even while protected, does not confer ownership after resuming.
resumed = {'lifetime_lock_held': False, 'all_pfns_were_checked': True,
           'uniform_type_was_seen': True, 'pages_allocated_to_caller': False,
           'dma_quiesced': False}
assert not resumed['pages_allocated_to_caller'] and not resumed['dma_quiesced']

print('PASS abstract memory lifetime: check/use, shared CPU locks and late notifier registration have counterexamples; reader/writer exclusion prevents modeled teardown; paused lock owner blocks; no ownership/DMA inference')
