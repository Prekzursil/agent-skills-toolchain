"""P0 census + claim statements for CNF-0154 (CNF-0140 stand-in)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def load_census() -> dict[str, Any]:
    return json.loads((FIXTURES / "p0_census.json").read_text(encoding="utf-8"))


def load_claims() -> list[dict[str, Any]]:
    claims = []
    for path in sorted((FIXTURES / "claims").glob("*.json")):
        claims.append(json.loads(path.read_text(encoding="utf-8")))
    return claims


def claim_by_id(claim_id: str) -> dict[str, Any]:
    for c in load_claims():
        if c["claim_id"] == claim_id:
            return c
    raise KeyError(claim_id)


def p0_ids() -> list[str]:
    return list(load_census()["p0"])
