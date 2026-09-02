"""Load TST-0317 fusion fixtures off disk."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def sources() -> list[dict[str, Any]]:
    return [load_json("source_alpha.json"), load_json("source_beta.json")]


def evidence() -> list[dict[str, Any]]:
    return load_json("evidence.json")


def cases() -> list[dict[str, Any]]:
    return load_json("cases.json")
