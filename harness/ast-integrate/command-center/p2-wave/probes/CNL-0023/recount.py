#!/usr/bin/env python3
"""Independent recount of justified vs unjustified non-equal weights.

Does not import validator.py. A disagreement with the author's tabulated
numbers blocks the unit.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hashutil import digest_file

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ALLOWED = frozenset({"charter_authority", "conflict_discount", "owner_decision"})
WEIGHT_MAX = 4.0


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def recount(spec: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    seats = spec.get("seats") if isinstance(spec.get("seats"), list) else []
    equal = 0
    justified = 0
    bad: list[dict[str, Any]] = []
    for seat in seats:
        if not isinstance(seat, dict):
            bad.append({"seat_id": "?", "why": "not-object"})
            continue
        sid = str(seat.get("seat_id") or "?")
        if "vote_weight" not in seat:
            equal += 1
            continue
        weight = _num(seat.get("vote_weight"))
        if weight is None or weight <= 0 or weight > WEIGHT_MAX:
            bad.append({"seat_id": sid, "why": "weight-invalid", "vote_weight": seat.get("vote_weight")})
            continue
        if weight == 1.0:
            equal += 1
            continue
        prov = seat.get("weight_provenance")
        if not isinstance(prov, dict):
            bad.append({"seat_id": sid, "why": "missing-provenance", "vote_weight": weight})
            continue
        klass = str(prov.get("justification_class") or "")
        if klass not in ALLOWED:
            bad.append({"seat_id": sid, "why": "class-not-allowed", "class": klass, "vote_weight": weight})
            continue
        expected = _num(prov.get("expected_weight"))
        if expected != weight:
            bad.append({"seat_id": sid, "why": "expected-mismatch", "vote_weight": weight})
            continue
        if klass == "conflict_discount" and not (weight < 1.0):
            bad.append({"seat_id": sid, "why": "conflict-not-below-one", "vote_weight": weight})
            continue
        rel = str(prov.get("source_path") or "").replace("\\", "/")
        src = root / rel
        if not src.is_file():
            bad.append({"seat_id": sid, "why": "source-missing", "path": rel})
            continue
        live = digest_file(src)
        if live != str(prov.get("source_sha256") or ""):
            bad.append({"seat_id": sid, "why": "digest-mismatch", "vote_weight": weight})
            continue
        if len(str(prov.get("challenge_path") or "").strip()) < 8:
            bad.append({"seat_id": sid, "why": "challenge-path-short", "vote_weight": weight})
            continue
        justified += 1
    return {
        "equal_weight": equal,
        "justified_non_equal": justified,
        "seats": len(seats),
        "unjustified": bad,
        "unjustified_count": len(bad),
        "unjustified_seat_ids": [row["seat_id"] for row in bad],
    }


def recount_fixture(name: str) -> dict[str, Any]:
    spec = json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))
    out = recount(spec)
    out["fixture"] = name
    out["spec_id"] = spec.get("id")
    return out
