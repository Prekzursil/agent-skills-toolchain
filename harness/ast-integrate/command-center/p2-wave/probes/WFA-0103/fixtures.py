"""Load WFA-0103 fusion fixtures off disk."""
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


def evidence_separated() -> list[dict[str, Any]]:
    return load_json("evidence_separated.json")


def evidence_tied_synthesize() -> list[dict[str, Any]]:
    return load_json("evidence_tied_synthesize.json")


def evidence_llm_basis() -> list[dict[str, Any]]:
    return load_json("evidence_llm_basis.json")


def tie_rule_text() -> str:
    return (HERE / "TIE-RULE.txt").read_text(encoding="utf-8")
