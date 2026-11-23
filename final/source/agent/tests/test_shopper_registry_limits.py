import pytest

from agent.session_registry import SESSION_TTL_SECONDS, SessionRegistry
from agent.shopper_access import ShopperAccess


def test_session_capacity_recovers_expired_slots_without_lookup():
    now = [0.0]
    registry = SessionRegistry(clock=lambda: now[0], capacity=2)
    registry.create()
    registry.create()
    with pytest.raises(OverflowError):
        registry.create()
    now[0] = SESSION_TTL_SECONDS + 1
    registry.create()
    assert len(registry._sessions) == 1
    for _ in range(10):
        now[0] += SESSION_TTL_SECONDS + 1
        registry.create()
    assert len(registry._expired_ids) <= 2


def test_browser_expiry_capacity_and_challenge_bounds():
    now = [0.0]
    access = ShopperAccess(clock=lambda: now[0], capacity=1)
    token, owner = access.create()
    with pytest.raises(OverflowError):
        access.create()
    challenges = [access.challenge(owner) for _ in range(4)]
    with pytest.raises(OverflowError):
        access.challenge(owner)
    assert access.consume_challenge(owner, challenges[0])
    assert not access.consume_challenge(owner, challenges[0])
    now[0] = 60
    assert not access.consume_challenge(owner, challenges[1])
    access.challenge(owner)
    now[0] = 86400
    assert access.resolve(token) is None
    access.create()
