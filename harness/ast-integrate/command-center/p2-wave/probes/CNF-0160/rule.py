#!/usr/bin/env python3
"""CNF-0160 recruitment rule: documented, executable, auditable.

Trigger (all clauses):
  1. Anthropic-side verdict != Codex/CNF-0154 verdict (vendors disagree).
  2. CNF-0155 could not settle the pair executably (outcome == IRREDUCIBLE).
  3. Escalated count so far is below the declared budget cap.

Budget:
  Default cap is 3 third-model recruitments per run (cost-aware).
  Only an actual recruitment (third rail available) consumes the cap.
  A missing rail does not consume budget and must not become a two-way vote.

Three-way split:
  When the third verdict equals neither vendor, the outcome is
  AMBIGUOUS-CLAIM — a signal about the CLAIM's ambiguity, not a
  majority / casting vote. The resolver never returns CONFIRMED,
  REFUTED, PARTIAL, or BLOCKED as a triangulation outcome.

If the third rail is unavailable: NOT-CHECKED with a named missing
prerequisite. Never silently fall back to a two-way vote.
"""
from __future__ import annotations

from typing import Any

UNIT_ID = "CNF-0160"
IRREDUCIBLE = "IRREDUCIBLE"
AMBIGUOUS_CLAIM = "AMBIGUOUS-CLAIM"
NOT_CHECKED = "NOT-CHECKED"
CONVERGENT_ANTHROPIC = "CONVERGENT-ANTHROPIC"
CONVERGENT_CODEX = "CONVERGENT-CODEX"
REDUNDANT_AGREEMENT = "REDUNDANT-AGREEMENT"

DEFAULT_BUDGET_CAP = 3

# Claim-level verdicts a casting/majority vote would emit. Forbidden here.
CASTING_VERDICTS = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "BLOCKED"}
)
TRIANGULATION_OUTCOMES = frozenset(
    {
        AMBIGUOUS_CLAIM,
        NOT_CHECKED,
        CONVERGENT_ANTHROPIC,
        CONVERGENT_CODEX,
        REDUNDANT_AGREEMENT,
    }
)

RULE = {
    "id": "CNF-0160-third-model-recruitment",
    "title": "Cost-aware third-model triangulation, recruited only where the two vendors disagree",
    "trigger": {
        "all_of": [
            "anthropic_verdict != codex_verdict",
            "cnf0155_outcome == IRREDUCIBLE",
            "escalated_count < budget.cap",
        ],
        "does_not_fire_when": [
            "vendors agree",
            "CNF-0155 already settled the pair by an executable tiebreak",
            "budget cap already consumed by prior recruitments this run",
        ],
    },
    "budget": {
        "cap": DEFAULT_BUDGET_CAP,
        "unit": "third-model recruitments per run",
        "consumes_on": "actual recruitment while a third rail is available",
        "does_not_consume_on": "missing-rail NOT-CHECKED (no model call)",
        "rationale": (
            "Third-model calls are the scarce resource. Cap=3 bounds cost "
            "on a disagreement ledger; remaining IRREDUCIBLE claims stay "
            "visible as budget-exhausted, never silently dropped."
        ),
    },
    "when_third_agrees_with_neither": {
        "outcome": AMBIGUOUS_CLAIM,
        "meaning": "signal about the CLAIM's ambiguity, not a casting vote",
        "forbids": [
            "majority vote among the three verdicts",
            "treating the third model as a tie-breaking caster",
            "collapsing to either two-vendor verdict",
        ],
    },
    "when_third_rail_unavailable": {
        "outcome": NOT_CHECKED,
        "emit": "named missing prerequisite",
        "forbids": ["silent two-way vote fallback"],
    },
}


def evaluate_trigger(
    entry: dict[str, Any], *, budget_remaining: int
) -> dict[str, Any]:
    """Evaluate trigger clauses for one claim. Always recorded, even if not fired."""
    anthropic = str(entry.get("anthropic_verdict") or "")
    codex = str(entry.get("codex_verdict") or "")
    cnf0155 = str(entry.get("cnf0155_outcome") or "")
    disagree = anthropic != codex and bool(anthropic) and bool(codex)
    unsettled = cnf0155 == IRREDUCIBLE
    budget_ok = int(budget_remaining) > 0
    clauses = {
        "vendors_disagree": disagree,
        "cnf0155_unsettled_irreducible": unsettled,
        "budget_remaining": budget_ok,
    }
    inhibit: list[str] = []
    if not disagree:
        inhibit.append("vendors-agree")
    if disagree and not unsettled:
        inhibit.append("cnf0155-settled-executably")
    if not budget_ok:
        inhibit.append("budget-exhausted")
    fired = all(clauses.values())
    return {
        "claim_id": entry.get("claim_id"),
        "anthropic_verdict": anthropic,
        "codex_verdict": codex,
        "cnf0155_outcome": cnf0155,
        "tiebreak_test_id": entry.get("tiebreak_test_id"),
        "clauses": clauses,
        "trigger_fired": fired,
        "inhibit_reasons": inhibit,
        "budget_remaining_before": int(budget_remaining),
    }


def resolve_three_way(anthropic: str, codex: str, third: str | None) -> str:
    """Map (A, Codex, third) to a triangulation outcome. Never a casting vote."""
    if third is None or str(third).strip() == "":
        return NOT_CHECKED
    t = str(third)
    if t == anthropic and t != codex:
        return CONVERGENT_ANTHROPIC
    if t == codex and t != anthropic:
        return CONVERGENT_CODEX
    if t != anthropic and t != codex:
        return AMBIGUOUS_CLAIM
    return REDUNDANT_AGREEMENT


def is_casting_vote(outcome: str) -> bool:
    return outcome in CASTING_VERDICTS
