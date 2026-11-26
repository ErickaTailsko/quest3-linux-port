"""Executable design model only. No kernel, ADB, restart or MMIO operations."""
from dataclasses import dataclass, field
GATES = frozenset({'image_verified','staging_reserved','retained_log_validated',
 'efi_runtime_absent','cpu_protocol_validated','dma_shutdown_validated',
 'handler_order_validated','module_lifetime_pinned','atomic_entry_validated'})
@dataclass
class Handoff:
    state: str = 'NEW'
    evidence: set = field(default_factory=set)
    events: list = field(default_factory=list)
    def prepare(self):
        if self.state != 'NEW': raise ValueError('invalid preparation state')
        self.state = 'PREPARED'
    def commit(self):
        if self.state != 'PREPARED': raise ValueError('invalid commit state')
        missing = GATES - self.evidence
        if missing: raise ValueError('unvalidated: '+','.join(sorted(missing)))
        self.state = 'COMMITTED'
        self.events.append('kernel_restart')
    def fail(self):
        if self.state in ('COMMITTED','FINAL'):
            self.state = 'RESET_FALLBACK'
            self.events.append('continue_restart_chain')
        elif self.state in ('NEW','PREPARED'):
            self.state = 'ABORTED'
            self.events.append('release_prepared_resources')
        else: raise ValueError('terminal state')
    def final_callback(self, matching_request, cpu_ready, dma_ready):
        if self.state != 'COMMITTED' or not matching_request:
            self.events.append('ignore_unrelated_restart')
            return
        if not (cpu_ready and dma_ready):
            self.fail()
            return
        self.state = 'FINAL'
        self.events.append('nonreturning_entry_required')

def test():
    for gate in GATES:
        m=Handoff(evidence=set(GATES)-{gate});m.prepare()
        try: m.commit()
        except ValueError: pass
        else: raise AssertionError(gate)
        assert m.state=='PREPARED' and not m.events
        m.fail();assert m.events==['release_prepared_resources']
    m=Handoff(evidence=set(GATES));m.prepare();m.commit();m.fail()
    assert m.state=='RESET_FALLBACK' and 'release_prepared_resources' not in m.events
    m=Handoff(evidence=set(GATES));m.prepare();m.commit()
    m.final_callback(False,True,True);assert m.state=='COMMITTED'
    m.final_callback(True,False,True);assert m.state=='RESET_FALLBACK'
    m=Handoff(evidence=set(GATES));m.prepare();m.commit()
    m.final_callback(True,True,False);assert m.state=='RESET_FALLBACK'
    m=Handoff(evidence=set(GATES));m.prepare();m.commit()
    m.final_callback(True,True,True);assert m.state=='FINAL'
    print('PASS: missing gates refuse commit; precommit cleanup; no postcommit rollback; unrelated restart ignored; final checks; entry model')
if __name__=='__main__': test()
