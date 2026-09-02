#!/usr/bin/env python3
"""Reject unjustified non-equal vote weights at spec validation.

Default suffrage is 1.0. A seat may declare vote_weight != 1.0 only with a
weight_provenance record whose class is allowed, whose expected_weight matches
the declared weight, and whose source_sha256 matches the justifying artifact
on disk. Validation never starts the council.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hashutil import digest_file

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ALLOWED_CLASSES = frozenset(
    {"charter_authority", "conflict_discount", "owner_decision"}
)
WEIGHT_MAX = 4.0
COUNCIL_RUNS = 0

CODE_UNJUSTIFIED = "UNJUSTIFIED_NON_EQUAL_WEIGHT"
CODE_CLASS = "PROVENANCE_CLASS_NOT_ALLOWED"
CODE_DIGEST = "PROVENANCE_DIGEST_MISMATCH"
CODE_MISSING_SRC = "PROVENANCE_SOURCE_MISSING"
CODE_WEIGHT_MISMATCH = "PROVENANCE_WEIGHT_MISMATCH"
CODE_CONFLICT = "CONFLICT_DISCOUNT_NOT_BELOW_ONE"
CODE_RANGE = "WEIGHT_OUT_OF_RANGE"
CODE_TYPE = "WEIGHT_NOT_NUMERIC"


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _finding(seat_id: str, weight: Any, code: str, detail: str) -> dict[str, Any]:
    return {
        "code": code,
        "detail": detail,
        "seat_id": seat_id,
        "vote_weight": weight,
    }


def validate_spec(spec: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    """Return ACCEPT/REJECT. Does not increment COUNCIL_RUNS."""
    root = repo or REPO
    seats = spec.get("seats")
    if not isinstance(seats, list) or not seats:
        return {
            "codes": ["SEATS_MISSING"],
            "council_ran": False,
            "equal_weight": 0,
            "justified_non_equal": 0,
            "seats": 0,
            "unjustified": [
                _finding("*", None, "SEATS_MISSING", "spec.seats must be a non-empty list")
            ],
            "verdict": "REJECT",
        }
    equal = 0
    justified = 0
    unjustified: list[dict[str, Any]] = []
    for seat in seats:
        if not isinstance(seat, dict):
            unjustified.append(_finding("?", None, CODE_TYPE, "seat is not an object"))
            continue
        seat_id = str(seat.get("seat_id") or "?")
        if "vote_weight" not in seat:
            equal += 1
            continue
        weight = _num(seat.get("vote_weight"))
        if weight is None:
            unjustified.append(
                _finding(seat_id, seat.get("vote_weight"), CODE_TYPE, "vote_weight is not a number")
            )
            continue
        if weight <= 0 or weight > WEIGHT_MAX:
            unjustified.append(
                _finding(
                    seat_id,
                    weight,
                    CODE_RANGE,
                    f"vote_weight {weight} outside (0, {WEIGHT_MAX}]",
                )
            )
            continue
        if weight == 1.0:
            equal += 1
            continue
        prov = seat.get("weight_provenance")
        if not isinstance(prov, dict):
            unjustified.append(
                _finding(
                    seat_id,
                    weight,
                    CODE_UNJUSTIFIED,
                    "non-equal weight has no weight_provenance; rejected before the council runs",
                )
            )
            continue
        klass = str(prov.get("justification_class") or "")
        if klass not in ALLOWED_CLASSES:
            unjustified.append(
                _finding(
                    seat_id,
                    weight,
                    CODE_CLASS,
                    f"justification_class {klass!r} is not in {sorted(ALLOWED_CLASSES)}",
                )
            )
            continue
        expected = _num(prov.get("expected_weight"))
        if expected is None or expected != weight:
            unjustified.append(
                _finding(
                    seat_id,
                    weight,
                    CODE_WEIGHT_MISMATCH,
                    f"expected_weight {prov.get('expected_weight')!r} != vote_weight {weight}",
                )
            )
            continue
        if klass == "conflict_discount" and not (weight < 1.0):
            unjustified.append(
                _finding(
                    seat_id,
                    weight,
                    CODE_CONFLICT,
                    "conflict_discount requires vote_weight < 1.0",
                )
            )
            continue
        rel = str(prov.get("source_path") or "").replace("\\", "/")
        src = root / rel
        if not src.is_file():
            unjustified.append(
                _finding(
                    seat_id,
                    weight,
                    CODE_MISSING_SRC,
                    f"source_path missing on disk: {rel}",
                )
            )
            continue
        live = digest_file(src)
        claimed = str(prov.get("source_sha256") or "")
        if live != claimed:
            unjustified.append(
                _finding(
                    seat_id,
                    weight,
                    CODE_DIGEST,
                    f"source_sha256 {claimed} != live {live}",
                )
            )
            continue
        challenge = str(prov.get("challenge_path") or "").strip()
        if len(challenge) < 8:
            unjustified.append(
                _finding(
                    seat_id,
                    weight,
                    CODE_UNJUSTIFIED,
                    "challenge_path missing; auditor cannot contest after the decision",
                )
            )
            continue
        justified += 1
    verdict = "ACCEPT" if not unjustified else "REJECT"
    return {
        "codes": [row["code"] for row in unjustified],
        "council_ran": False,
        "equal_weight": equal,
        "justified_non_equal": justified,
        "seats": len(seats),
        "unjustified": unjustified,
        "verdict": verdict,
    }


def load_fixture(name: str) -> dict[str, Any]:
    path = HERE / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


def run_if_valid(spec: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    """Start the council only after ACCEPT. Planted-bad must never increment COUNCIL_RUNS."""
    global COUNCIL_RUNS
    result = validate_spec(spec, repo=repo)
    if result["verdict"] != "ACCEPT":
        return {"council_ran": False, "validation": result}
    COUNCIL_RUNS += 1
    return {"council_ran": True, "validation": result}


def schema_errors(spec: dict[str, Any]) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = json.loads((HERE / "vote-weight.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in sorted(validator.iter_errors(spec), key=lambda e: list(e.absolute_path))
    ]
