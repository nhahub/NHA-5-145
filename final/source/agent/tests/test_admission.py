from concurrent.futures import ThreadPoolExecutor

import pytest

from agent.admission.store import AdmissionDenied, InvitationStore


def test_fixed_window_revocation_and_quota_survive_reopen(tmp_path):
    path = tmp_path / "admission.sqlite"
    identity = InvitationStore.initialize(path)
    clock = [100.0]
    store = InvitationStore(path, identity, clock=lambda: clock[0])
    invitation, code = store.issue(110, 150, redemptions=1, sessions=1)
    with pytest.raises(AdmissionDenied):
        store.redeem(code, "browser-a")
    clock[0] = 110
    store.redeem(code, "browser-a")
    store.redeem(code, "browser-a")
    reopened = InvitationStore(path, identity, clock=lambda: clock[0])
    with pytest.raises(AdmissionDenied):
        reopened.redeem(code, "browser-b")
    reopened.allocate_session("browser-a")
    with pytest.raises(AdmissionDenied):
        reopened.allocate_session("browser-a")
    assert reopened.allowed("browser-a")
    reopened.revoke(invitation)
    assert not store.allowed("browser-a")
    assert code not in path.read_bytes().decode("latin1")
    with pytest.raises(FileExistsError):
        InvitationStore.initialize(path)
    _, next_code = store.issue(110, 150, redemptions=1, sessions=1)
    clock[0] = 150
    with pytest.raises(AdmissionDenied):
        store.redeem(next_code, "browser-c")


def test_concurrent_last_redemption_is_atomic(tmp_path):
    path = tmp_path / "admission.sqlite"
    identity = InvitationStore.initialize(path)
    store = InvitationStore(path, identity, clock=lambda: 100)
    _, code = store.issue(90, 120, redemptions=1, sessions=2)

    def redeem(subject):
        try:
            InvitationStore(path, identity, clock=lambda: 100).redeem(code, subject)
            return True
        except AdmissionDenied:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(redeem, ("a", "b"))) == [False, True]


def test_missing_or_corrupt_storage_never_creates_fresh_access(tmp_path):
    path = tmp_path / "admission.sqlite"
    identity = InvitationStore.initialize(path)
    store = InvitationStore(path, identity, clock=lambda: 100)
    _, code = store.issue(90, 120, redemptions=1, sessions=1)
    store.redeem(code, "a")
    path.unlink()
    assert not store.allowed("a")
    assert not path.exists()
    path.write_bytes(b"corrupt")
    with pytest.raises(AdmissionDenied):
        store.redeem(code, "a")


def test_replacement_code_never_refunds_the_old_redemption(tmp_path):
    path = tmp_path / "admission.sqlite"
    store = InvitationStore(path, InvitationStore.initialize(path), clock=lambda: 100)
    first, code = store.issue(90, 120, redemptions=1, sessions=2)
    store.redeem(code, "a")
    _, other = store.issue(90, 120, redemptions=1, sessions=2)
    with pytest.raises(AdmissionDenied):
        store.redeem(other, "a")
    store.revoke(first)
    store.redeem(other, "a")
    assert store.status()[0]["used_redemptions"] == 1
