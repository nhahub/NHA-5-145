import pytest


@pytest.fixture(autouse=True)
def isolated_agent_state_file(tmp_path, monkeypatch):
    """In-process Agent apps in evaluation tests never write the default `work/` session file.

    Services started as separate processes get their own state files from
    `eval.services.service_environment`.
    """
    monkeypatch.setattr("agent.state_store.default_state_path", lambda: tmp_path / "agent-state.db")
