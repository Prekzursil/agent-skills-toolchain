#!/usr/bin/env python3
"""Shared loaders and an independent majority recompute for IMP-0367 probes.

The independent majority here is a second signal: it does not import
tools.council.sensitivity.aggregate_majority.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MODULE = REPO / "tools/council/sensitivity.py"
ART = REPO / "command-center/receipts/IMP-0367.json"
FIX_DECISIVE = HERE / "fixtures/evidence-decisive.json"
FIX_NSENS = HERE / "fixtures/n-sensitive.json"
FIX_BELOW = HERE / "fixtures/default-below.json"
REQUIRED_RECEIPT_KEYS = (
    "unit_id",
    "artifact_paths",
    "spec_anchor",
    "evidence",
    "test_ids",
    "negative_control_ids",
    "reviewer_verdict",
    "residual_unknowns",
)
TIE = "TIE"
NO_QUORUM = "NO-QUORUM"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def independent_majority(votes: list[str]) -> str:
    if not votes:
        return NO_QUORUM
    counts: dict[str, int] = {}
    for vote in votes:
        counts[vote] = counts.get(vote, 0) + 1
    top = max(counts.values())
    winners = [k for k, n in counts.items() if n == top]
    if len(winners) != 1:
        return TIE
    return winners[0]


def independent_curve(question: dict) -> list[dict]:
    seats = question["seats"]
    curve = []
    for n in range(1, len(seats) + 1):
        votes = [str(s["vote"]) for s in seats[:n]]
        tally: dict[str, int] = {}
        for v in votes:
            tally[v] = tally.get(v, 0) + 1
        curve.append(
            {
                "n": n,
                "decision": independent_majority(votes),
                "tally": dict(sorted(tally.items())),
            }
        )
    return curve


def independent_stabilisation(curve: list[dict]) -> dict:
    decisions = [p["decision"] for p in curve]
    distinct = []
    for d in decisions:
        if d not in distinct:
            distinct.append(d)
    n_star = curve[-1]["n"]
    star_i = len(curve) - 1
    for i, point in enumerate(curve):
        if all(decisions[j] == decisions[i] for j in range(i, len(decisions))):
            n_star = point["n"]
            star_i = i
            break
    tail = len(curve) - star_i
    n_sensitive = len(distinct) > 1
    return {
        "stabilisation_n": n_star,
        "stable_decision": decisions[star_i],
        "trivial_stabilisation": n_sensitive and tail == 1,
        "n_sensitive": n_sensitive,
        "distinct_decisions": distinct,
    }


def require_receipt() -> dict:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise SystemExit("FAILED:IMP-0367 receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:IMP-0367 receipt not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0367 self-declared {st}")
    if "SUCCESS:IMP-0367" not in text:
        raise SystemExit("FAILED:IMP-0367 sentinel absent")
    if doc.get("unit_id") != "IMP-0367":
        raise SystemExit(f"FAILED:IMP-0367 unit_id {doc.get('unit_id')}")
    for key in REQUIRED_RECEIPT_KEYS:
        if key not in doc:
            raise SystemExit(f"FAILED:IMP-0367 receipt missing {key}")
    paths = doc.get("artifact_paths")
    if not isinstance(paths, list) or not paths:
        raise SystemExit("FAILED:IMP-0367 artifact_paths empty")
    return doc


def public_by_id(doc: dict) -> dict:
    exp = doc.get("experiment") or {}
    rows = exp.get("questions") or []
    return {r["question_id"]: r for r in rows if isinstance(r, dict)}
