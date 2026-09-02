#!/usr/bin/env python3
"""Apply the CNF-0160 recruitment rule to a disagreement ledger."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rule import (
    AMBIGUOUS_CLAIM,
    DEFAULT_BUDGET_CAP,
    NOT_CHECKED,
    RULE,
    evaluate_trigger,
    is_casting_vote,
    resolve_three_way,
)

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
MISSING_PREREQUISITE = "third-vendor-rail-unauthenticated"


def load_ledger(path: Path | None = None) -> dict[str, Any]:
    p = path or (FIXTURES / "disagreement-ledger.json")
    return json.loads(p.read_text(encoding="utf-8"))


def load_thirds(path: Path | None = None) -> dict[str, str]:
    p = path or (FIXTURES / "third-verdicts.json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in (doc.get("verdicts") or doc).items()}


def apply_rule(
    ledger: dict[str, Any],
    thirds: dict[str, str],
    *,
    rail_available: bool,
    cap: int = DEFAULT_BUDGET_CAP,
) -> dict[str, Any]:
    """Recruit a third model only where the trigger fires and a rail exists.

    Records a trigger evaluation for every claim, including those not escalated.
    """
    entries = list(ledger.get("entries") or [])
    budget_remaining = int(cap)
    evaluations: list[dict[str, Any]] = []
    escalated = 0
    ambiguous = 0
    not_checked = 0

    for entry in entries:
        trig = evaluate_trigger(entry, budget_remaining=budget_remaining)
        claim_id = str(entry.get("claim_id") or "")
        planted = thirds.get(claim_id)
        rec: dict[str, Any] = {
            **trig,
            "planted_third_verdict": planted,
            "recruited": False,
            "rail_available": bool(rail_available),
            "triangulation_outcome": None,
            "missing_prerequisite": None,
            "two_way_fallback_used": False,
            "casting_vote_used": False,
        }
        if not trig["trigger_fired"]:
            rec["disposition"] = "not-escalated"
            evaluations.append(rec)
            continue

        if not rail_available:
            rec["disposition"] = "qualified-but-rail-missing"
            rec["triangulation_outcome"] = NOT_CHECKED
            rec["missing_prerequisite"] = MISSING_PREREQUISITE
            rec["two_way_fallback_used"] = False
            not_checked += 1
            evaluations.append(rec)
            continue

        rec["recruited"] = True
        rec["disposition"] = "recruited"
        outcome = resolve_three_way(
            str(entry.get("anthropic_verdict") or ""),
            str(entry.get("codex_verdict") or ""),
            planted,
        )
        if is_casting_vote(outcome):
            rec["casting_vote_used"] = True
            rec["disposition"] = "illegal-casting-vote"
        rec["triangulation_outcome"] = outcome
        budget_remaining -= 1
        escalated += 1
        if outcome == AMBIGUOUS_CLAIM:
            ambiguous += 1
        if outcome == NOT_CHECKED:
            not_checked += 1
        evaluations.append(rec)

    recruited_ids = [e["claim_id"] for e in evaluations if e["recruited"]]
    not_escalated = [e for e in evaluations if not e["recruited"]]
    return {
        "rule_id": RULE["id"],
        "budget_cap": int(cap),
        "rail_available": bool(rail_available),
        "claims_considered": len(evaluations),
        "escalated_count": escalated,
        "escalated_within_cap": escalated <= int(cap),
        "ambiguous_claim_count": ambiguous,
        "not_checked_count": not_checked,
        "recruited_claim_ids": recruited_ids,
        "not_escalated_claim_ids": [e["claim_id"] for e in not_escalated],
        "two_way_fallback_anywhere": any(
            e.get("two_way_fallback_used") for e in evaluations
        ),
        "casting_vote_anywhere": any(
            e.get("casting_vote_used") for e in evaluations
        ),
        "evaluations": evaluations,
    }


def independent_should_escalate(entry: dict[str, Any], *, budget_remaining: int) -> bool:
    """Reviewer re-derivation of the trigger (must not read recruit dispositions)."""
    return bool(
        evaluate_trigger(entry, budget_remaining=budget_remaining)["trigger_fired"]
    )
