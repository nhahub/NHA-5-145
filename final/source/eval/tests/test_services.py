from pathlib import Path

import pytest

from eval.services import ROOT, service_commands, service_environment


def test_node_services_are_launched_as_owned_processes() -> None:
    commands = service_commands(Path("node"))

    assert commands[1][0] == "node"
    assert Path(commands[1][1]).as_posix().endswith("store/node_modules/tsx/dist/cli.mjs")
    assert commands[2][0] == "node"
    assert Path(commands[2][1]).as_posix().endswith("panel/node_modules/vite/bin/vite.js")
    assert commands[2][2] == str(ROOT / "panel")


def test_local_evaluation_services_bind_only_to_loopback() -> None:
    commands = service_commands(Path("node"))

    assert commands[0][commands[0].index("--host") + 1] == "127.0.0.1"
    assert commands[2][commands[2].index("--host") + 1] == "127.0.0.1"


def test_local_evaluation_explicitly_selects_the_scripted_model() -> None:
    environment = service_environment({"PATH": "test-path"})

    assert environment["PATH"] == "test-path"
    assert environment["LLM_PROVIDER"] == "scripted"
    assert environment["LLM_MODEL"] == "scripted-v1"


def test_real_browser_evaluation_requires_explicit_real_provider_selection() -> None:
    selected = service_environment(
        {"LLM_PROVIDER": "groq", "LLM_MODEL": "openai/gpt-oss-120b"}, real_model=True
    )
    assert selected["LLM_PROVIDER"] == "groq"
    assert selected["LLM_MODEL"] == "openai/gpt-oss-120b"
    with pytest.raises(ValueError, match="real provider"):
        service_environment(
            {"LLM_PROVIDER": "scripted", "LLM_MODEL": "scripted-v1"}, real_model=True
        )


def test_local_evaluation_keeps_its_state_in_the_given_temporary_directory() -> None:
    environment = service_environment({"PATH": "p"}, state_directory=Path("tmp-state"))

    assert Path(environment["AGENT_STATE_FILE"]) == Path("tmp-state") / "agent-state.sqlite"
    assert Path(environment["COPILOT_STATE_DB"]) == Path("tmp-state") / "storefront-state.sqlite"
