#!/usr/bin/env python3
"""Allocation-only design model with fake providers. No kernel/ADB operations."""
from dataclasses import dataclass, field


@dataclass
class Transaction:
    state: str = 'NEW'
    owned: list = field(default_factory=list)
    boot_ready: bool = False
    payload_written: bool = False

    @property
    def can_unload(self):
        return not self.owned and self.state != 'RETAINED_FOR_REVIEW'

    def acquire(self, api, *, fits, exports, identity, lifetime, consent):
        if self.state != 'NEW':
            raise ValueError('transaction cannot be repeated')
        if not all((fits, exports, identity, lifetime, consent)):
            self.state = 'REJECTED'
            return False
        self.state = 'ACQUIRING'
        for kind in ('default-cma-image', 'buddy-initrd', 'buddy-dtb'):
            token = api.allocate(kind)
            if token is None:
                if self._release_owned(api):
                    self.state = 'FAILED_CLEAN'
                return False
            self.owned.append((kind, token))
        self.state = 'OWNED'
        return True

    def _release_owned(self, api):
        while self.owned:
            kind, token = self.owned[-1]
            if not api.release(kind, token):
                # Do not lose the token, retry blindly or allow unload after
                # an unexpected release failure. This is a terminal model state.
                self.state = 'RETAINED_FOR_REVIEW'
                return False
            self.owned.pop()
        return True

    def release(self, api):
        if self.state != 'OWNED':
            raise ValueError('not an owned releasable transaction')
        if self._release_owned(api):
            self.state = 'RELEASED'


class FakeProviders:
    def __init__(self, fail_alloc=None, fail_release=None):
        self.fail_alloc = fail_alloc
        self.fail_release = fail_release
        self.events = []
        self.live = {}

    def allocate(self, kind):
        self.events.append(('allocate', kind))
        if kind == self.fail_alloc:
            return None
        assert kind not in self.live
        token = object()
        self.live[kind] = token
        return token

    def release(self, kind, token):
        self.events.append(('release', kind))
        assert self.live.get(kind) is token  # Never release unowned/failed calls.
        if kind == self.fail_release:
            return False
        del self.live[kind]
        return True


def test():
    gates = dict(fits=True, exports=True, identity=True, lifetime=True, consent=True)
    for gate in gates:
        api = FakeProviders(); transaction = Transaction()
        assert not transaction.acquire(api, **{**gates,gate:False})
        assert transaction.state == 'REJECTED' and not api.events and transaction.can_unload
    for index, kind in enumerate(('default-cma-image','buddy-initrd','buddy-dtb')):
        api = FakeProviders(fail_alloc=kind); transaction = Transaction()
        assert not transaction.acquire(api, **gates)
        assert transaction.state == 'FAILED_CLEAN' and not api.live and transaction.can_unload
        assert sum(action == 'allocate' for action, _ in api.events) == index+1
        assert sum(action == 'release' for action, _ in api.events) == index
        assert ('release',kind) not in api.events
    api = FakeProviders(); transaction = Transaction()
    assert transaction.acquire(api, **gates) and not transaction.can_unload
    assert not transaction.boot_ready and not transaction.payload_written
    transaction.release(api)
    assert transaction.state == 'RELEASED' and transaction.can_unload and not api.live
    old = list(api.events)
    try:transaction.release(api)
    except ValueError:pass
    else:raise AssertionError('double release accepted')
    try:transaction.acquire(api, **gates)
    except ValueError:pass
    else:raise AssertionError('repeated acquisition accepted')
    assert api.events == old
    api = FakeProviders(fail_release='default-cma-image'); transaction = Transaction()
    assert transaction.acquire(api, **gates)
    transaction.release(api)
    assert transaction.state == 'RETAINED_FOR_REVIEW' and not transaction.can_unload
    assert len(transaction.owned) == len(api.live) == 1
    assert not transaction.boot_ready
    print('PASS allocation-only ownership model: gates reject before calls, one attempt per provider, reverse partial rollback, no unowned/double release, retained failure blocks unload and no payload/boot action')


if __name__ == '__main__':
    test()
