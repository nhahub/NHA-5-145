import json
from pathlib import Path

FIXTURES = Path(__file__).parents[2] / "protocol" / "v1" / "fixtures"


def load_fixture(path: str) -> object:
    return json.loads((FIXTURES / path).read_text(encoding="utf-8"))
