#!/usr/bin/env python3
"""CNL-0018 mechanism: vendor diversity under a real quota ceiling.

Diversity objective: a second paid vendor is bought for independence of
failure domains (outage, safety-layer, training-correlation, quota pool),
not for costume diversity. A roster is vendor-diverse only when it has
>=2 distinct vendors AND >=2 distinct base models AND no base model is
seated twice. Same-base-model-twice is therefore NOT vendor-diverse even
when the vendor labels differ.

Quota figures in live subscriptions are NOT measured here. Fixtures use
integer remaining-call counters that the tests declare before scoring.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

RISK_TIERS = ("discovery", "standard", "high-stakes", "irreversible")
RISK_RANK = {
    "discovery": 0,
    "standard": 1,
    "high-stakes": 2,
    "irreversible": 3,
}
# Vendor diversity is mandatory from high-stakes upward. Below that it is
# optional (discovery) or recommended-with-waiver (standard). This is a
# seating rule, not a procurement authorization to buy a second subscription.
MANDATORY_FROM_TIER = "high-stakes"
MANDATORY_RANK = RISK_RANK[MANDATORY_FROM_TIER]

EVT_QUOTA_EXHAUSTED = "QUOTA-EXHAUSTED"
EVT_SUBSTITUTION_REFUSED = "SUBSTITUTION-REFUSED"
EVT_SEAT_SKIPPED = "SEAT-SKIPPED"
EVT_INDEPENDENCE_VOID = "INDEPENDENCE-VOID"

POLICY_OPTIONAL = "optional"
POLICY_RECOMMENDED = "recommended"
POLICY_MANDATORY = "mandatory"


def _norm(token: Any) -> str:
    return str(token or "").strip().lower()


def vendor_id(seat: dict) -> str:
    return _norm(seat.get("vendor"))


def base_model_id(seat: dict) -> str:
    raw = seat.get("base_model")
    if raw is None or str(raw).strip() == "":
        raw = seat.get("model")
    return _norm(raw)


def diversity_policy(risk_tier: str) -> str:
    if risk_tier not in RISK_RANK:
        raise ValueError(f"unknown risk_tier:{risk_tier}")
    rank = RISK_RANK[risk_tier]
    if rank >= MANDATORY_RANK:
        return POLICY_MANDATORY
    if rank == RISK_RANK["standard"]:
        return POLICY_RECOMMENDED
    return POLICY_OPTIONAL


def vendor_diversity_report(roster: list[dict]) -> dict[str, Any]:
    if not isinstance(roster, list) or len(roster) < 1:
        return {
            "vendor_diverse": False,
            "same_base_model_twice": False,
            "reason": "empty-or-invalid-roster",
            "distinct_vendors": [],
            "distinct_base_models": [],
            "duplicate_base_models": [],
            "vendor_counts": {},
            "base_model_counts": {},
        }
    vendors = [vendor_id(s) for s in roster if isinstance(s, dict)]
    models = [base_model_id(s) for s in roster if isinstance(s, dict)]
    vcount = Counter(vendors)
    mcount = Counter(models)
    duplicate_models = sorted(m for m, n in mcount.items() if n >= 2)
    same_twice = len(duplicate_models) > 0
    diverse = (
        len(set(vendors)) >= 2
        and len(set(models)) >= 2
        and not same_twice
        and all(v for v in vendors)
        and all(m for m in models)
    )
    reason = "vendor-diverse"
    if same_twice:
        reason = "same-base-model-twice"
    elif len(set(vendors)) < 2:
        reason = "single-vendor"
    elif len(set(models)) < 2:
        reason = "single-base-model"
    return {
        "vendor_diverse": diverse,
        "same_base_model_twice": same_twice,
        "reason": reason,
        "distinct_vendors": sorted(set(vendors)),
        "distinct_base_models": sorted(set(models)),
        "duplicate_base_models": duplicate_models,
        "vendor_counts": dict(sorted(vcount.items())),
        "base_model_counts": dict(sorted(mcount.items())),
        "seat_count": len(roster),
    }


def seating_decision(roster: list[dict], risk_tier: str) -> dict[str, Any]:
    report = vendor_diversity_report(roster)
    policy = diversity_policy(risk_tier)
    if report["vendor_diverse"]:
        action = "seat"
        waiver = None
    elif policy == POLICY_MANDATORY:
        action = "refuse"
        waiver = None
    else:
        action = "seat-with-waiver"
        waiver = {
            "independence_assumption": "VOID",
            "policy": policy,
            "reason": report["reason"],
        }
    return {
        "risk_tier": risk_tier,
        "policy": policy,
        "action": action,
        "waiver": waiver,
        "report": report,
    }


def _forbidden_same_vendor_reseat(
    roster: list[dict], substitute: dict
) -> bool:
    """True when the substitute's vendor is already on the roster.

    That is the failure the catalog names: silently re-seating the same
    (still-funded) vendor to paper over an exhausted second vendor.
    """
    existing = {vendor_id(s) for s in roster}
    return vendor_id(substitute) in existing


def simulate_council(
    roster: list[dict],
    remaining: dict[str, int],
    n_rounds: int,
    risk_tier: str,
    *,
    attempt_same_vendor_reseat: bool = False,
) -> dict[str, Any]:
    """Run a scripted council against a remaining-call map.

    remaining maps vendor_id -> calls left. One speaking turn costs 1.
    When a seat's vendor is exhausted: emit QUOTA-EXHAUSTED (loud),
    refuse same-vendor reseat, preserve turns already taken, skip the
    exhausted seat. The council does not claim independence after that.
    """
    if n_rounds < 1:
        raise ValueError("n_rounds must be >= 1")
    seats = deepcopy(roster)
    quota = { _norm(k): int(v) for k, v in remaining.items() }
    events: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    reseated = False
    independence_void = False
    terminal = "SUCCESS"

    def snapshot() -> dict[str, Any]:
        return {
            "turns": deepcopy(turns),
            "rounds_completed_turns": len(turns),
            "seat_ids_that_spoke": [t["seat_id"] for t in turns],
            "quota_remaining": dict(quota),
        }

    seating = seating_decision(seats, risk_tier)
    if seating["action"] == "refuse":
        return {
            "terminal": "REFUSED",
            "independence_void": True,
            "reseated_same_vendor": False,
            "events": [
                {
                    "type": EVT_INDEPENDENCE_VOID,
                    "loud": True,
                    "reason": seating["report"]["reason"],
                    "policy": seating["policy"],
                }
            ],
            "partial_artifact": snapshot(),
            "seating": seating,
            "final_roster_vendors": [vendor_id(s) for s in seats],
        }
    if seating["waiver"] is not None:
        independence_void = True
        events.append(
            {
                "type": EVT_INDEPENDENCE_VOID,
                "loud": True,
                "reason": seating["waiver"]["reason"],
                "policy": seating["policy"],
            }
        )

    exhausted_seats: set[str] = set()
    for round_i in range(n_rounds):
        for seat in list(seats):
            sid = str(seat.get("id") or "")
            if sid in exhausted_seats:
                continue
            vid = vendor_id(seat)
            left = int(quota.get(vid, 0))
            if left <= 0:
                independence_void = True
                terminal = "DEGRADED"
                events.append(
                    {
                        "type": EVT_QUOTA_EXHAUSTED,
                        "loud": True,
                        "vendor": vid,
                        "seat_id": sid,
                        "round": round_i,
                        "independence_void": True,
                        "partial_preserved": True,
                    }
                )
                exhausted_seats.add(sid)
                if attempt_same_vendor_reseat:
                    donor = next(
                        (s for s in seats if int(quota.get(vendor_id(s), 0)) > 0),
                        None,
                    )
                    if donor is not None:
                        substitute = {
                            "id": f"{sid}-reseat",
                            "vendor": donor.get("vendor"),
                            "model": donor.get("model"),
                            "base_model": donor.get("base_model") or donor.get("model"),
                        }
                        if _forbidden_same_vendor_reseat(roster, substitute):
                            events.append(
                                {
                                    "type": EVT_SUBSTITUTION_REFUSED,
                                    "loud": True,
                                    "reason": "same-vendor-reseating-forbidden",
                                    "exhausted_vendor": vid,
                                    "substitute_vendor": vendor_id(substitute),
                                    "substitute_id": substitute["id"],
                                }
                            )
                        else:
                            seats.append(substitute)
                            reseated = True
                events.append(
                    {
                        "type": EVT_SEAT_SKIPPED,
                        "seat_id": sid,
                        "vendor": vid,
                        "round": round_i,
                    }
                )
                policy = diversity_policy(risk_tier)
                if policy == POLICY_MANDATORY:
                    return {
                        "terminal": "DEGRADED",
                        "independence_void": True,
                        "reseated_same_vendor": reseated,
                        "events": events,
                        "partial_artifact": snapshot(),
                        "seating": seating,
                        "final_roster_vendors": [vendor_id(s) for s in seats],
                    }
                continue
            quota[vid] = left - 1
            turns.append(
                {
                    "round": round_i,
                    "seat_id": sid,
                    "vendor": vid,
                    "base_model": base_model_id(seat),
                    "quota_after": quota[vid],
                }
            )

    loud_events = [e for e in events if e.get("type") == EVT_QUOTA_EXHAUSTED]
    return {
        "terminal": terminal,
        "independence_void": independence_void,
        "reseated_same_vendor": reseated,
        "events": events,
        "partial_artifact": snapshot(),
        "seating": seating,
        "final_roster_vendors": [vendor_id(s) for s in seats],
        "quota_exhausted_fired": len(loud_events) > 0,
        "quota_exhausted_count": len(loud_events),
    }


def independent_model_recount(roster: list[dict]) -> dict[str, Any]:
    """Second signal: Counter over the base_model field, no diversity helper."""
    models = [base_model_id(s) for s in roster if isinstance(s, dict)]
    counts = Counter(models)
    return {
        "counts": dict(sorted(counts.items())),
        "duplicates": sorted(m for m, n in counts.items() if n >= 2),
        "distinct": sorted(set(models)),
    }


def independent_quota_recount(
    roster: list[dict], remaining: dict[str, int], n_rounds: int
) -> dict[str, Any]:
    """Second signal: walk turns until a vendor would go negative.

    Does not call simulate_council. Declares when the first exhaustion
    would occur and how many turns complete before it.
    """
    quota = { _norm(k): int(v) for k, v in remaining.items() }
    completed = 0
    first_exhaust: dict[str, Any] | None = None
    for round_i in range(n_rounds):
        for seat in roster:
            vid = vendor_id(seat)
            if quota.get(vid, 0) <= 0:
                first_exhaust = {
                    "round": round_i,
                    "seat_id": seat.get("id"),
                    "vendor": vid,
                    "turns_before": completed,
                }
                return {
                    "would_exhaust": True,
                    "first": first_exhaust,
                    "turns_before": completed,
                }
            quota[vid] = quota.get(vid, 0) - 1
            completed += 1
    return {"would_exhaust": False, "first": None, "turns_before": completed}


# Fixtures declared before scoring (catalog: threshold/fixture-first).
ROSTER_DIVERSE = [
    {
        "id": "seat-a",
        "vendor": "anthropic",
        "model": "claude-opus",
        "base_model": "claude-opus",
    },
    {
        "id": "seat-b",
        "vendor": "openai",
        "model": "gpt-4o",
        "base_model": "gpt-4o",
    },
]
ROSTER_SAME_BASE_TWICE = [
    {
        "id": "seat-a",
        "vendor": "anthropic",
        "model": "claude-opus",
        "base_model": "claude-opus",
    },
    {
        "id": "seat-b",
        "vendor": "anthropic",
        "model": "claude-opus-4",
        "base_model": "claude-opus",
    },
]
ROSTER_SAME_BASE_CROSS_VENDOR = [
    {
        "id": "seat-a",
        "vendor": "openai",
        "model": "gpt-4o",
        "base_model": "gpt-4o",
    },
    {
        "id": "seat-b",
        "vendor": "azure",
        "model": "gpt-4o",
        "base_model": "gpt-4o",
    },
]
ROSTER_SAME_VENDOR_DIFF_MODEL = [
    {
        "id": "seat-a",
        "vendor": "anthropic",
        "model": "claude-opus",
        "base_model": "claude-opus",
    },
    {
        "id": "seat-b",
        "vendor": "anthropic",
        "model": "claude-sonnet",
        "base_model": "claude-sonnet",
    },
]

# Mid-council exhaustion: 2 seats x 3 rounds = 6 turns. openai remaining=1
# means seat-b speaks once (round 0) then exhausts. anthropic remaining is
# large so it is the donor a silent reseat would abuse.
QUOTA_BAD = {"anthropic": 100, "openai": 1}
QUOTA_GOOD = {"anthropic": 100, "openai": 100}
N_ROUNDS = 3


def run_all_controls() -> dict[str, Any]:
    diverse = vendor_diversity_report(ROSTER_DIVERSE)
    same_twice = vendor_diversity_report(ROSTER_SAME_BASE_TWICE)
    cross = vendor_diversity_report(ROSTER_SAME_BASE_CROSS_VENDOR)
    same_vendor = vendor_diversity_report(ROSTER_SAME_VENDOR_DIFF_MODEL)
    recount_bad = independent_model_recount(ROSTER_SAME_BASE_TWICE)
    recount_good = independent_model_recount(ROSTER_DIVERSE)
    quota_bad = simulate_council(
        ROSTER_DIVERSE,
        QUOTA_BAD,
        N_ROUNDS,
        "high-stakes",
        attempt_same_vendor_reseat=True,
    )
    quota_good = simulate_council(
        ROSTER_DIVERSE,
        QUOTA_GOOD,
        N_ROUNDS,
        "high-stakes",
        attempt_same_vendor_reseat=True,
    )
    quota_recount_bad = independent_quota_recount(
        ROSTER_DIVERSE, QUOTA_BAD, N_ROUNDS
    )
    quota_recount_good = independent_quota_recount(
        ROSTER_DIVERSE, QUOTA_GOOD, N_ROUNDS
    )
    seating_mandatory_bad = seating_decision(
        ROSTER_SAME_BASE_TWICE, "high-stakes"
    )
    seating_optional_bad = seating_decision(
        ROSTER_SAME_BASE_TWICE, "discovery"
    )
    return {
        "diverse": diverse,
        "same_base_twice": same_twice,
        "same_base_cross_vendor": cross,
        "same_vendor_diff_model": same_vendor,
        "recount_same_base_twice": recount_bad,
        "recount_diverse": recount_good,
        "quota_bad": quota_bad,
        "quota_good": quota_good,
        "quota_recount_bad": quota_recount_bad,
        "quota_recount_good": quota_recount_good,
        "seating_mandatory_same_base": seating_mandatory_bad,
        "seating_optional_same_base": seating_optional_bad,
        "mandatory_from_tier": MANDATORY_FROM_TIER,
        "risk_tiers": list(RISK_TIERS),
    }
