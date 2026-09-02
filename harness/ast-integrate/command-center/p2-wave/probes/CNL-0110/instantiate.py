#!/usr/bin/env python3
"""Bind the requirements-council preset to a fixture task."""
from __future__ import annotations

from typing import Any

from preset import REQUIRED_CLASSES, fingerprint, preset as load_preset


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def contradict(a: dict, b: dict) -> bool:
    return a["id"] in b.get("conflicts_with", []) or b["id"] in a.get(
        "conflicts_with", []
    )


def reject_blend(outcome: dict) -> dict:
    """Negative control: fire on a blended requirement for a contradicting pair."""
    fires = outcome.get("kind") == "blended-requirement"
    return {
        "fires": fires,
        "rejects": "blended-requirement for a contradicting pair",
        "on_state": (
            "a pair collapsed into one requirement that claims to satisfy both wants"
        ),
        "verbatim": (
            "FIRES when pair_outcome.kind == 'blended-requirement'; "
            "SILENT when kind is 'irreducible-disagreement' or 'reconciled'."
        ),
    }


def seat_roster(task: dict, p: dict | None = None) -> dict[str, Any]:
    p = p or load_preset()
    required = tuple(p["delta"]["balance_metric"]["required_classes"])
    by_class: dict[str, list[dict]] = {c: [] for c in required}
    for cand in task["candidates"]:
        cls = cand["class"]
        if cls in by_class:
            by_class[cls].append(cand)
    roster: list[dict] = []
    missing: list[str] = []
    counts = {c: 0 for c in required}
    for cls in required:
        if by_class[cls]:
            seat = dict(by_class[cls][0], role=cls)
            roster.append(seat)
            counts[cls] = 1
        else:
            missing.append(cls)
    balanced = not missing
    return {
        "roster": roster,
        "counts": counts,
        "missing_classes": missing,
        "balanced": balanced,
        "balance_metric": p["delta"]["balance_metric"]["id"],
        "blocked_elicit": (not balanced)
        and p["delta"]["anti_failure"]["underfilled_class_blocks_elicit"],
    }


def instantiate(task: dict, p: dict | None = None) -> dict[str, Any]:
    p = p or load_preset()
    seating = seat_roster(task, p)
    base = {
        "ok": False,
        "task_id": task.get("id"),
        "seating": seating,
        "roster": seating["roster"],
        "protocol_schedule": p["delta"]["protocol_schedule"],
        "voting": {
            "elicit": p["delta"]["voting"]["elicit"]["rule"],
            "reconcile": p["delta"]["voting"]["reconcile"]["rule"],
        },
        "stopping": {
            "elicit": p["delta"]["stopping"]["elicit"]["done_when"],
            "reconcile": p["delta"]["stopping"]["reconcile"]["done_when"],
        },
        "fingerprint": fingerprint(p),
    }
    if seating["blocked_elicit"]:
        base["reason"] = "underfilled-class"
        return base

    seated_classes = {s["class"] for s in seating["roster"]}
    ledger = []
    for want in task["wants"]:
        if want["class"] in seated_classes:
            ledger.append(
                {
                    "id": want["id"],
                    "class": want["class"],
                    "statement": want["statement"],
                    "conflicts_with": list(want.get("conflicts_with") or []),
                    "phase": "p-elicit",
                }
            )

    classes_with_wants = {w["class"] for w in ledger}
    elicit_complete = set(REQUIRED_CLASSES) <= classes_with_wants

    pairs: list[tuple[dict, dict]] = []
    seen: set[tuple[str, str]] = set()
    for i, a in enumerate(ledger):
        for b in ledger[i + 1 :]:
            if not contradict(a, b):
                continue
            key = _pair_key(a["id"], b["id"])
            if key in seen:
                continue
            seen.add(key)
            pairs.append((a, b))

    rewrites = list(task.get("proposed_rewrites") or [])
    pair_outcomes = []
    for a, b in pairs:
        key = _pair_key(a["id"], b["id"])
        candidates = [
            r for r in rewrites if _pair_key(r["pair"][0], r["pair"][1]) == key
        ]
        originators = {a["class"], b["class"]}
        accepted = None
        attempts = []
        for r in candidates:
            ok = originators <= set(r.get("accepted_by") or [])
            attempts.append({"rewrite_id": r["id"], "accepted": ok})
            if ok and accepted is None:
                accepted = r
        if accepted is not None:
            kind = "reconciled"
            outcome_type = p["delta"]["outcomes"]["reconciled_pair"]
        elif not attempts:
            kind = "incomplete"
            outcome_type = p["delta"]["outcomes"]["untried_pair"]
        else:
            kind = "irreducible-disagreement"
            outcome_type = p["delta"]["outcomes"]["unreconcilable_pair"]
        pair_outcomes.append(
            {
                "pair": [a["id"], b["id"]],
                "pair_key": list(key),
                "originators": sorted(originators),
                "kind": kind,
                "outcome_type": outcome_type,
                "attempts": attempts,
                "information_gain_positive": False,
                "rewrite": None if accepted is None else accepted["rewrite"],
            }
        )

    planted_blend = {
        "pair": ["W-plain", "W-erase"],
        "kind": "blended-requirement",
        "statement": "Store plaintext and also erase on request, as one requirement.",
    }
    irreducible = next(
        (
            o
            for o in pair_outcomes
            if tuple(o["pair_key"]) == ("W-erase", "W-plain")
        ),
        {"kind": "irreducible-disagreement"},
    )
    base.update(
        {
            "ok": True,
            "elicit_complete": elicit_complete,
            "want_ledger": ledger,
            "pair_outcomes": pair_outcomes,
            "negative_control": {
                "planted_blend": reject_blend(planted_blend),
                "known_irreducible": reject_blend(irreducible),
            },
        }
    )
    return base
