"""CNL-0096 detector: hard-cap exhaustion vs genuine no-decision.

Pathology is present when a council hits its hard cap without a decision and
the emitted record is either (a) labelled as a deliberative non-decision
variant or (b) missing the preserved-work payload. The detector is silent
when the cap-hit record is the distinct exhausted_without_decision kind
with termination_cause=hard_cap and non-empty preserved work, or when the
run never hit the cap.
"""
from __future__ import annotations

from typing import Any

EXHAUSTED_KIND = "exhausted_without_decision"
DECISION_KINDS = frozenset({"decision", "conditional_decision"})
SPEC_NON_DECISION = frozenset(
    {
        "no-decision",
        "irreducible_disagreement",
        "dissent-with-minority-report",
        "proof_of_impossibility",
    }
)
PRESERVED_WORK = (
    "transcript",
    "last_positions",
    "vote_snapshot",
    "information_gain_by_round",
)


def cap_state(run: dict[str, Any]) -> dict[str, Any]:
    cap = run.get("hard_cap") or {}
    value = int(cap["value"])
    rounds = int(run["rounds_consumed"])
    remaining = max(0, value - rounds)
    return {
        "kind": str(cap.get("kind") or ""),
        "value": value,
        "rounds_consumed": rounds,
        "cap_remaining": remaining,
        "cap_hit": rounds >= value,
    }


def missing_work(run: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in PRESERVED_WORK:
        val = run.get(key)
        if val is None:
            missing.append(key)
            continue
        if isinstance(val, (list, dict, str)) and len(val) == 0:
            missing.append(key)
    return missing


def distinguisher(run: dict[str, Any]) -> tuple[str, str, int]:
    """Signal B: three-tuple independent of detect().fired.

    Genuine no-decision and cap-exhaustion must differ on this tuple.
    """
    cap = cap_state(run)
    outcome = run.get("outcome") or {}
    return (
        str(outcome.get("kind") or ""),
        str(outcome.get("termination_cause") or ""),
        int(cap["cap_remaining"]),
    )


def detect(run: dict[str, Any]) -> dict[str, Any]:
    """Signal A: fire/silent codes over a single run record."""
    codes: list[str] = []
    cap = cap_state(run)
    outcome = run.get("outcome") or {}
    kind = str(outcome.get("kind") or "")
    cause = str(outcome.get("termination_cause") or "")
    missing = missing_work(run)
    has_decision = kind in DECISION_KINDS

    if cap["cap_hit"] and not has_decision:
        if kind != EXHAUSTED_KIND:
            codes.append("masquerade-as-non-exhausted-kind")
        if kind in SPEC_NON_DECISION:
            codes.append(f"masquerade-as-spec-variant:{kind}")
        if cause != "hard_cap":
            codes.append("termination-cause-not-hard-cap")
        if missing:
            codes.append("preserved-work-lost:" + ",".join(missing))
    elif (not cap["cap_hit"]) and kind == EXHAUSTED_KIND:
        codes.append("false-exhaustion-claim")

    return {
        "id": str(run.get("id") or ""),
        "fired": bool(codes),
        "codes": codes,
        "cap": cap,
        "kind": kind,
        "termination_cause": cause,
        "distinguisher": list(distinguisher(run)),
        "work_missing": missing,
        "has_decision": has_decision,
    }
