"""The State Store contract: one suite every adapter must pass.

An adapter's test module subclasses `StateStoreContract` and implements `make_store`:
it returns a store whose notion of "now" is `clock()` and a callable `reopen()` giving
another store on the same data (a second process on the same file or table). The SQLite file
store passes it in `test_state_store.py`; a DynamoDB adapter (ticket 04) plugs in the same way.
"""

import pytest

from agent.state_store import MAX_RECORD_BYTES, RecordTooLarge, RevisionConflict


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class StateStoreContract:
    def make_store(self, tmp_path, clock):
        """Return (store, reopen); `reopen()` is a second store on the same data."""
        raise NotImplementedError

    @pytest.fixture
    def clock(self):
        return Clock()

    @pytest.fixture
    def store(self, tmp_path, clock):
        return self.make_store(tmp_path, clock)[0]

    def test_a_written_record_reads_back_with_its_revision(self, store, clock):
        revision = store.write("k", {"a": [1, "نص"]}, clock.now + 100, None)

        record = store.read("k")

        assert revision == 1
        assert (record.value, record.revision) == ({"a": [1, "نص"]}, 1)

    def test_a_missing_record_reads_as_none(self, store):
        assert store.read("nobody") is None

    def test_a_conditional_write_bumps_the_revision(self, store, clock):
        store.write("k", {"n": 1}, clock.now + 100, None)

        assert store.write("k", {"n": 2}, clock.now + 100, 1) == 2
        assert store.read("k").value == {"n": 2}

    def test_a_write_with_a_stale_revision_is_refused_and_changes_nothing(self, store, clock):
        store.write("k", {"n": 1}, clock.now + 100, None)
        store.write("k", {"n": 2}, clock.now + 100, 1)

        with pytest.raises(RevisionConflict):
            store.write("k", {"n": 3}, clock.now + 100, 1)

        assert store.read("k").value == {"n": 2}

    def test_creating_an_existing_record_is_refused(self, store, clock):
        store.write("k", {"n": 1}, clock.now + 100, None)

        with pytest.raises(RevisionConflict):
            store.write("k", {"n": 9}, clock.now + 100, None)

    def test_updating_a_missing_record_is_refused(self, store, clock):
        with pytest.raises(RevisionConflict):
            store.write("k", {"n": 1}, clock.now + 100, 1)

    def test_delete_removes_the_record_and_a_missing_one_is_not_an_error(self, store, clock):
        store.write("k", {"n": 1}, clock.now + 100, None)

        store.delete("k")
        store.delete("k")

        assert store.read("k") is None

    def test_a_record_expires_at_its_expiry_time(self, store, clock):
        store.write("k", {"n": 1}, clock.now + 100, None)

        clock.now += 99
        assert store.read("k") is not None
        clock.now += 1
        assert store.read("k") is None

    def test_an_expired_record_can_be_created_again_from_scratch(self, store, clock):
        store.write("k", {"n": 1}, clock.now + 10, None)
        clock.now += 11

        assert store.write("k", {"n": 2}, clock.now + 10, None) == 1
        assert store.read("k").value == {"n": 2}

    def test_every_write_sets_the_expiry_again(self, store, clock):
        store.write("k", {"n": 1}, clock.now + 10, None)
        clock.now += 9
        store.write("k", {"n": 1}, clock.now + 10, 1)

        clock.now += 9
        assert store.read("k") is not None

    def test_records_are_kept_apart_by_key(self, store, clock):
        store.write("a", {"who": "a"}, clock.now + 100, None)
        store.write("b", {"who": "b"}, clock.now + 100, None)

        assert store.read("a").value == {"who": "a"}
        assert store.read("b").value == {"who": "b"}

    def test_a_second_store_on_the_same_data_sees_the_records_and_conflicts(self, tmp_path, clock):
        first, reopen = self.make_store(tmp_path, clock)
        second = reopen()
        first.write("k", {"n": 1}, clock.now + 100, None)

        assert second.read("k").value == {"n": 1}
        with pytest.raises(RevisionConflict):
            second.write("k", {"n": 2}, clock.now + 100, None)

    def test_an_oversized_record_is_refused_and_not_saved(self, store, clock):
        too_big = {"text": "x" * (MAX_RECORD_BYTES + 1)}

        with pytest.raises(RecordTooLarge):
            store.write("k", too_big, clock.now + 100, None)

        assert store.read("k") is None

    def test_a_record_just_under_the_guard_is_saved(self, store, clock):
        store.write("k", {"text": "x" * (MAX_RECORD_BYTES - 100)}, clock.now + 100, None)

        assert store.read("k") is not None
