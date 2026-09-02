#!/usr/bin/env python3
"""CNL-0066 abstention semantics and strategic-abstention detection.

Decision denominator is the frozen seated set (seated_n0). Present-and-voting
is a report field only; using it as threshold_basis is a protocol violation.

Principled abstention is a structured record. A pivotal abstention that fails
that record is strategic. Strategic abstention cannot park a decision.
"""
from __future__ import annotations

from typing import Any

# CNL-0066-RULE: decision denominator is seated_n0, never present-and-voting
ALLOWED_BASIS = frozenset({"seated", "eligible_snapshot"})
FORBIDDEN_BASIS = frozenset({"present_and_voting", "pv", "voting_present"})

PRINCIPLED_REASONS = frozenset(
    {"NO_EXPERTISE", "CONFLICT_OF_INTEREST", "INSUFFICIENT_EVIDENCE"}
)
GENERIC_REASONS = frozenset(
    {"", "NONE", "NO_COMMENT", "PREFER_NOT", "GENERIC", "N/A", "NA"}
)

POLICY_PARK = "PARK_PRINCIPLED_ELSE_COUNT_AS_NO"
POLICY_COUNT_NO = "COUNT_AS_NO"
ALLOWED_POLICIES = frozenset({POLICY_PARK, POLICY_COUNT_NO})


def _tags(xs: Any) -> set[str]:
    if not xs:
        return set()
    return {str(x) for x in xs}


def expertise_overlap(seat: dict, question: dict) -> set[str]:
    return _tags(seat.get("expertise_tags")) & _tags(question.get("required_domains"))


def prior_on_class(seat: dict, question: dict) -> bool:
    qid = str(question.get("question_class_id") or "")
    if not qid:
        return False
    for row in seat.get("prior_positions") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("question_class_id") or "") != qid:
            continue
        if str(row.get("kind") or "") in {"YES", "NO"}:
            return True
    return False


def structured_claim(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    what = str(obj.get("what") or "").strip()
    why = str(obj.get("why_blocks_vote") or "").strip()
    return bool(what) and bool(why)


def structured_predicate(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    field = str(obj.get("field") or "").strip()
    op = str(obj.get("op") or "").strip()
    return bool(field) and bool(op)


def reason_code(ballot: dict) -> str:
    return str(ballot.get("reason_code") or "").strip().upper().replace(" ", "_")


def principled_fields_ok(
    ballot: dict, seat: dict, question: dict
) -> tuple[bool, list[str]]:
    """Return (ok, failure codes). CNL-0066-DISC: both-direction discriminator."""
    fails: list[str] = []
    if str(ballot.get("kind") or "") != "ABSTAIN":
        return False, ["not-abstain"]
    code = reason_code(ballot)
    if code not in PRINCIPLED_REASONS:
        fails.append("reason-not-principled-class")
    if not structured_claim(ballot.get("missing_claim")):
        fails.append("missing-claim-unstructured")
    if not structured_predicate(ballot.get("would_unpark_if")):
        fails.append("would-unpark-if-unstructured")
    if code == "NO_EXPERTISE" and expertise_overlap(seat, question):
        fails.append("no-expertise-but-domain-overlap")
    if code == "NO_EXPERTISE" and prior_on_class(seat, question):
        fails.append("no-expertise-but-prior-position")
    return (len(fails) == 0), fails


def validate_protocol(question: dict, seats: list[dict]) -> dict[str, Any]:
    basis = str(question.get("threshold_basis") or "").strip().lower()
    n0 = int(question.get("seated_n0") or 0)
    thr = int(question.get("threshold_yes") or 0)
    policy = str(question.get("abstention_policy") or POLICY_PARK)
    violations: list[str] = []
    if basis in FORBIDDEN_BASIS or basis not in ALLOWED_BASIS:
        violations.append(f"illegal-threshold-basis:{basis or 'missing'}")
    if n0 != len(seats):
        violations.append(f"seated-n0-mismatch:{n0}!={len(seats)}")
    if n0 < 1:
        violations.append("empty-seated-set")
    if thr < 1 or (n0 and thr > n0):
        violations.append(f"threshold-yes-out-of-range:{thr}")
    if policy not in ALLOWED_POLICIES:
        violations.append(f"illegal-abstention-policy:{policy}")
    fired = bool(violations)
    return {
        "fired": fired,
        "silent": not fired,
        "violations": violations,
        "basis": basis,
        "seated_n0": n0,
        "threshold_yes": thr,
        "abstention_policy": policy,
    }


def yes_count(ballots: list[dict]) -> int:
    return sum(1 for b in ballots if str(b.get("kind") or "") == "YES")


def present_and_voting_count(ballots: list[dict]) -> int:
    return sum(1 for b in ballots if str(b.get("kind") or "") in {"YES", "NO"})


def is_pivotal(ballots: list[dict], seat_id: str, threshold_yes: int) -> bool:
    """Pivotal iff this non-YES seat switching to YES would cross threshold_yes."""
    kinds = {
        str(b.get("seat") or ""): str(b.get("kind") or "") for b in ballots
    }
    if kinds.get(seat_id) == "YES":
        return False
    yes = yes_count(ballots)
    return yes < threshold_yes <= (yes + 1)


def classify_abstention(
    ballot: dict,
    seat: dict,
    question: dict,
    ballots: list[dict],
) -> dict[str, Any]:
    ok, fails = principled_fields_ok(ballot, seat, question)
    thr = int(question.get("threshold_yes") or 0)
    pivotal = is_pivotal(ballots, str(ballot.get("seat") or ""), thr)
    overlap = sorted(expertise_overlap(seat, question))
    prior = prior_on_class(seat, question)
    generic = reason_code(ballot) in GENERIC_REASONS
    if ok:
        cls = "PRINCIPLED"
        fire = False
    elif pivotal:
        # CNL-0066-STRAT: pivotal + not-principled => strategic (fail closed)
        cls = "STRATEGIC"
        fire = True
    else:
        cls = "UNDETERMINED"
        fire = False
    return {
        "seat": ballot.get("seat"),
        "kind": "ABSTAIN",
        "class": cls,
        "strategic_fire": fire,
        "pivotal": pivotal,
        "principled_ok": ok,
        "principled_fails": fails,
        "expertise_overlap": overlap,
        "prior_on_class": prior,
        "generic_reason": generic,
        "reason_code": reason_code(ballot),
    }


def resolve(
    question: dict, seats: list[dict], ballots: list[dict]
) -> dict[str, Any]:
    proto = validate_protocol(question, seats)
    by_seat = {str(s.get("id") or ""): s for s in seats}
    rows: list[dict[str, Any]] = []
    principled_ids: list[str] = []
    strategic_ids: list[str] = []
    undetermined_ids: list[str] = []
    for ballot in ballots:
        kind = str(ballot.get("kind") or "")
        sid = str(ballot.get("seat") or "")
        seat = by_seat.get(sid) or {}
        if kind != "ABSTAIN":
            rows.append(
                {
                    "seat": sid,
                    "kind": kind,
                    "class": "VOTE",
                    "strategic_fire": False,
                    "pivotal": False,
                }
            )
            continue
        row = classify_abstention(ballot, seat, question, ballots)
        rows.append(row)
        if row["class"] == "PRINCIPLED":
            principled_ids.append(sid)
        elif row["class"] == "STRATEGIC":
            strategic_ids.append(sid)
        else:
            undetermined_ids.append(sid)

    yes = yes_count(ballots)
    n0 = len(seats)
    thr = int(question.get("threshold_yes") or 0)
    pv_den = present_and_voting_count(ballots)
    policy = str(question.get("abstention_policy") or POLICY_PARK)
    if proto["fired"]:
        decision = "INVALID-PROTOCOL"
    elif principled_ids and policy == POLICY_PARK:
        decision = "PARKED"
    elif yes >= thr:
        decision = "PASS"
    else:
        decision = "FAIL"

    shrinking_trap = {
        "present_and_voting_yes": yes,
        "present_and_voting_den": pv_den,
        "present_and_voting_ratio": (yes / pv_den) if pv_den else None,
        "present_and_voting_meets_two_thirds": bool(
            pv_den and (yes / pv_den) >= (2.0 / 3.0)
        ),
        "seated_yes": yes,
        "seated_den": n0,
        "seated_meets_threshold_yes": yes >= thr,
        "decision_uses_seated_not_pv": True,
    }
    return {
        "protocol": proto,
        "rows": rows,
        "principled_ids": principled_ids,
        "strategic_ids": strategic_ids,
        "undetermined_ids": undetermined_ids,
        "strategic_fire": bool(strategic_ids),
        "yes": yes,
        "no": sum(1 for b in ballots if str(b.get("kind") or "") == "NO"),
        "abstain": sum(1 for b in ballots if str(b.get("kind") or "") == "ABSTAIN"),
        "seated_n0": n0,
        "threshold_yes": thr,
        "decision": decision,
        "shrinking_trap": shrinking_trap,
        "policy": policy,
    }
