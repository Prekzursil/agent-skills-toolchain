"""Load IMP-0185 fusion fixtures off disk."""
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


def evidence_complete() -> list[dict[str, Any]]:
    return load_json("evidence_complete.json")


def evidence_missing_rank_beta() -> list[dict[str, Any]]:
    return load_json("evidence_missing_rank_beta.json")


def evidence_empty_run_id() -> list[dict[str, Any]]:
    return load_json("evidence_empty_run_id.json")


def evidence_reputation_only() -> list[dict[str, Any]]:
    return load_json("evidence_reputation_only.json")
