import pytest


@pytest.fixture(autouse=True)
def isolated_agent_state_file(tmp_path, monkeypatch):
    """Ordinary tests never share (or write to) the default `work/` session file."""
    monkeypatch.setattr("agent.state_store.default_state_path", lambda: tmp_path / "agent-state.db")


@pytest.fixture(autouse=True)
def no_default_storefront_catalogue(monkeypatch):
    """The default catalogue reader would reach whatever Storefront runs on the developer's
    machine; tests that need a catalogue pass their own reader or client."""
    import httpx

    async def unavailable(self):
        raise httpx.ConnectError("no catalogue in tests")

    monkeypatch.setattr("agent.catalogue.HttpCatalogueReader.read", unavailable)
