"""Prior objects: locked, evidence-backed belief state. Not a role label."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures.json"

STANCE_MAP = {
    "for": 1.0,
    "pro": 1.0,
    "against": -1.0,
    "con": -1.0,
    "plus": 1.0,
    "minus": -1.0,
}


def evidence_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def commitment_payload(prior: dict[str, Any]) -> str:
    return json.dumps(
        {
            "axis": prior["axis"],
            "polarity": round(float(prior["polarity"]), 6),
            "evidence_id": prior["evidence_id"],
            "evidence_sha256": prior["evidence_sha256"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def commitment_hash(prior: dict[str, Any]) -> str:
    return hashlib.sha256(commitment_payload(prior).encode("utf-8")).hexdigest()


def hydrate_prior(prior: dict[str, Any], bodies: dict[str, str]) -> dict[str, Any]:
    out = dict(prior)
    eid = str(out["evidence_id"])
    if eid not in bodies:
        raise KeyError(f"unknown evidence_id {eid}")
    out["evidence_sha256"] = evidence_sha256(bodies[eid])
    out["commitment_hash"] = commitment_hash(out)
    return out


def hydrate_seat(seat: dict[str, Any], bodies: dict[str, str]) -> dict[str, Any]:
    out = dict(seat)
    if isinstance(out.get("prior"), dict):
        out["prior"] = hydrate_prior(out["prior"], bodies)
    return out


def load_fixtures(path: Path | None = None) -> dict[str, Any]:
    doc = json.loads((path or FIXTURES).read_text(encoding="utf-8"))
    bodies = dict(doc["evidence_bodies"])
    rosters = {}
    for key, roster in doc["rosters"].items():
        seats = [hydrate_seat(s, bodies) for s in roster["seats"]]
        rosters[key] = {**roster, "seats": seats}
    return {**doc, "rosters": rosters}


def stance_polarity(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        if v > 0:
            return 1.0
        if v < 0:
            return -1.0
        return 0.0
    key = str(value).strip().lower()
    if key in STANCE_MAP:
        return STANCE_MAP[key]
    raise ValueError(f"unmapped assigned_stance {value!r}")


def prior_polarity(seat: dict[str, Any]) -> float:
    prior = seat.get("prior")
    if not isinstance(prior, dict):
        return 0.0
    return float(prior.get("polarity") or 0.0)


def prior_confidence(seat: dict[str, Any]) -> float:
    prior = seat.get("prior")
    if not isinstance(prior, dict):
        return 0.0
    c = float(prior.get("confidence") or 0.0)
    return min(1.0, max(0.0, c))


def verify_commitment(seat: dict[str, Any]) -> bool:
    prior = seat.get("prior")
    if not isinstance(prior, dict):
        return False
    expected = commitment_hash(prior)
    return expected == str(prior.get("commitment_hash") or "")
