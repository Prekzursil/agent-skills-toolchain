"""Shared fixture loader for IMP-0158 probes and library tests."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def load_json(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def twin_pair() -> tuple[dict, dict, dict]:
    """Same candidate document; unknown vs first-party evidence."""
    candidate = load_json("candidate-twin.json")
    unknown = load_json("evidence-unknown.json")
    first_party = load_json("evidence-first-party.json")
    return candidate, unknown, first_party
