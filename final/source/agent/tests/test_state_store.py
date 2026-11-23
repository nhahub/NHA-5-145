"""The Agent State Store's SQLite-file adapter, against the shared storage contract."""

import pytest

from agent.state_store import SqliteStateStore, StateStoreError, configured_state_store
from agent.tests.state_store_contract import StateStoreContract


class TestSqliteStateStore(StateStoreContract):
    def make_store(self, tmp_path, clock):
        path = tmp_path / "state.db"
        return SqliteStateStore(path, clock=clock), lambda: SqliteStateStore(path, clock=clock)


def test_the_store_creates_its_folder_and_file(tmp_path):
    path = tmp_path / "nested" / "state.db"

    SqliteStateStore(path).write("k", {}, 9e12, None)

    assert path.exists()


def test_an_unopenable_file_fails_visibly(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")

    with pytest.raises(StateStoreError):
        SqliteStateStore(blocker / "state.db").read("k")


def test_the_file_store_is_the_default_and_memory_can_be_chosen(tmp_path):
    assert isinstance(configured_state_store({}), SqliteStateStore)
    assert isinstance(
        configured_state_store({"AGENT_STATE_FILE": str(tmp_path / "x.db")}), SqliteStateStore
    )
    assert configured_state_store({"AGENT_STATE_STORE": "memory"}) is None
