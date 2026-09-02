"""CNL-0020 catch-up partition: what a mid-run recruit may see.

A late seat gets the context incumbents earned (charter, constraints,
evidence released by join-round, unique argument claims) and is refused
the social-proof channels that would let it copy the standing majority
(tally, majority label, per-seat votes, chair rec, claim frequencies).

The first position is a function of (catch-up brief, private prior) only.
Flipping the standing majority while holding evidence and prior fixed
must not change that position. A planted leak of the majority must make
leak_check FIRE. A starved brief must make completeness_check FIRE.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

DIALS_9 = (
    "model",
    "vendor",
    "expertise",
    "role",
    "authority",
    "vote_weight",
    "tools",
    "effort",
    "context",
)

WITHHELD_KEYS = frozenset(
    {
        "standing_tally",
        "standing_majority",
        "majority_label",
        "per_seat_votes",
        "chair_recommendation",
        "running_consensus",
        "claim_frequency",
        "leaning",
        "winning_side",
        "vote_share",
    }
)

LEAK_TEXT = re.compile(
    r"\b(standing[_\s-]?majority|majority\s+voted|current\s+consensus\s+is|"
    r"tally\s*:|chair\s+recommends|winning\s+side)\b",
    re.IGNORECASE,
)

PRIOR_WEIGHT = 2.0
EVIDENCE_WEIGHT = 1.0
CLAIM_WEIGHT = 0.3


def _walk_keys(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.append(str(k))
            found.extend(_walk_keys(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_keys(item))
    return found


def _walk_strings(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            found.extend(_walk_strings(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_strings(item))
    elif isinstance(obj, str):
        found.append(obj)
    return found


def leak_check(brief: dict) -> dict:
    """FIRE when the catch-up brief carries a withheld social-proof channel."""
    keys = _walk_keys(brief)
    hit_keys = sorted({k for k in keys if k in WITHHELD_KEYS})
    text_hits: list[str] = []
    for s in _walk_strings(brief):
        m = LEAK_TEXT.search(s)
        if m:
            text_hits.append(m.group(0))
    fired = bool(hit_keys or text_hits)
    return {
        "fired": fired,
        "code": "ANCHOR_LEAK" if fired else "SILENT",
        "hit_keys": hit_keys,
        "text_hits": text_hits[:8],
    }


def completeness_check(brief: dict, incumbent_evidence_ids: list[str]) -> dict:
    """FIRE when the newcomer is asked to vote without earned context."""
    missing_dials = [d for d in DIALS_9 if d not in (brief.get("newcomer_mandate") or {})]
    got = {str(e.get("id")) for e in (brief.get("evidence_at_join_round") or []) if isinstance(e, dict)}
    missing_ev = [i for i in incumbent_evidence_ids if i not in got]
    claims = brief.get("argument_claims_redacted")
    missing_claims = not isinstance(claims, list)
    starved = (not got and bool(incumbent_evidence_ids)) or bool(missing_ev)
    fired = bool(missing_dials or starved or missing_claims or not brief.get("question"))
    return {
        "fired": fired,
        "code": "CONTEXT_STARVED" if fired else "SILENT",
        "missing_dials": missing_dials,
        "missing_evidence_ids": missing_ev,
        "missing_claims_field": missing_claims,
    }


def may_cast_first_position(
    brief: dict, incumbent_evidence_ids: list[str], acked: bool
) -> dict:
    leak = leak_check(brief)
    complete = completeness_check(brief, incumbent_evidence_ids)
    if leak["fired"]:
        return {"allowed": False, "reason": leak["code"], "leak": leak, "completeness": complete}
    if complete["fired"]:
        return {
            "allowed": False,
            "reason": complete["code"],
            "leak": leak,
            "completeness": complete,
        }
    if not acked:
        return {
            "allowed": False,
            "reason": "CATCHUP_UNACKED",
            "leak": leak,
            "completeness": complete,
        }
    return {"allowed": True, "reason": "OK", "leak": leak, "completeness": complete}


def _polarity(label: str) -> int:
    u = str(label or "").upper()
    if u in {"ACCEPT", "YES", "FOR", "+1", "1"}:
        return 1
    if u in {"REJECT", "NO", "AGAINST", "-1"}:
        return -1
    return 0


def first_position(brief: dict, prior: str) -> str:
    """Deterministic proxy for a newcomer's first position.

    Reads evidence polarities and unique claim polarities plus the private
    prior. Does not read tally/majority even if a caller left them on the
    brief — leak_check is the detector for that state; this function is the
    independence behaviour on a clean brief.
    """
    score = PRIOR_WEIGHT * _polarity(prior)
    for e in brief.get("evidence_at_join_round") or []:
        if isinstance(e, dict):
            score += EVIDENCE_WEIGHT * float(e.get("polarity") or 0)
    for c in brief.get("argument_claims_redacted") or []:
        if isinstance(c, dict):
            score += CLAIM_WEIGHT * _polarity(c.get("polarity"))
    return "ACCEPT" if score >= 0 else "REJECT"


def _unique_claims(raw_claims: list[dict]) -> list[dict]:
    """Deduplicate by claim_id. Frequency and seat ids are dropped (anchoring)."""
    seen: dict[str, dict] = {}
    for c in raw_claims:
        cid = str(c.get("claim_id") or "")
        if not cid or cid in seen:
            continue
        seen[cid] = {
            "claim_id": cid,
            "text": str(c.get("text") or ""),
            "polarity": str(c.get("polarity") or ""),
        }
    return list(seen.values())


def build_catchup_brief(council: dict, newcomer: dict, leak: bool = False) -> dict:
    """Project the CNL-0006 lattice slice a recruit is allowed to see."""
    join_round = int(council["join_round"])
    released = [
        deepcopy(e)
        for e in council.get("evidence") or []
        if int(e.get("released_round") or 0) <= join_round
    ]
    raw_claims = []
    for arg in council.get("arguments") or []:
        if int(arg.get("round") or 0) <= join_round:
            raw_claims.append(
                {
                    "claim_id": arg.get("claim_id"),
                    "text": arg.get("text"),
                    "polarity": arg.get("polarity"),
                    "seat_id": arg.get("seat_id"),
                }
            )
    brief = {
        "question": council["question"],
        "constraints": deepcopy(council.get("constraints") or []),
        "join_round": join_round,
        "incumbent_round_count": join_round,
        "evidence_at_join_round": [
            {"id": e["id"], "text": e.get("text", ""), "polarity": e.get("polarity", 0)}
            for e in released
        ],
        "argument_claims_redacted": _unique_claims(raw_claims),
        "newcomer_mandate": {d: newcomer[d] for d in DIALS_9},
        "newcomer_seat_id": newcomer["seat_id"],
        "trigger": council.get("scale_trigger") or "min_to_max",
    }
    if leak:
        brief["standing_majority"] = council["standing_majority"]
        brief["standing_tally"] = deepcopy(council.get("standing_tally") or {})
        brief["chair_recommendation"] = council.get("chair_recommendation")
    return brief


def incumbent_evidence_ids(council: dict) -> list[str]:
    join_round = int(council["join_round"])
    return [
        str(e["id"])
        for e in council.get("evidence") or []
        if int(e.get("released_round") or 0) <= join_round
    ]


def fixture_good(*, majority: str = "ACCEPT") -> tuple[dict, dict]:
    """Known-good late-arrival: balanced evidence, withheld tally."""
    other = "REJECT" if majority == "ACCEPT" else "ACCEPT"
    council = {
        "question": "Ship the migration in this window?",
        "constraints": ["no-secret-in-artifact", "byte-identical replay"],
        "join_round": 2,
        "scale_trigger": "min_to_max_roster",
        "min_seats": 3,
        "max_seats": 5,
        "standing_majority": majority,
        "standing_tally": {majority: 3, other: 0},
        "chair_recommendation": majority,
        "evidence": [
            {
                "id": "ev-risk",
                "released_round": 1,
                "text": "Rollback path is untested on the live estate.",
                "polarity": -1,
            },
            {
                "id": "ev-need",
                "released_round": 1,
                "text": "The current loader drops overlay order under duplicate ids.",
                "polarity": 1,
            },
        ],
        "arguments": [
            {
                "claim_id": "c-need",
                "round": 1,
                "seat_id": "s1",
                "text": "Ship: the overlay-order defect is live.",
                "polarity": "ACCEPT",
            },
            {
                "claim_id": "c-need",
                "round": 1,
                "seat_id": "s2",
                "text": "Ship: the overlay-order defect is live.",
                "polarity": "ACCEPT",
            },
            {
                "claim_id": "c-risk",
                "round": 2,
                "seat_id": "s3",
                "text": "Wait: rollback is untested.",
                "polarity": "REJECT",
            },
        ],
    }
    newcomer = {
        "seat_id": "s-late",
        "model": "opus",
        "vendor": "anthropic",
        "expertise": "migrations",
        "role": "skeptic",
        "authority": "vote",
        "vote_weight": 1,
        "tools": ["read", "grep"],
        "effort": "standard",
        "context": "catchup",
        "prior": "REJECT",
    }
    return council, newcomer


def fixture_starved() -> tuple[dict, dict, dict]:
    council, newcomer = fixture_good()
    brief = build_catchup_brief(council, newcomer, leak=False)
    brief["evidence_at_join_round"] = []
    return council, newcomer, brief


def run_late_arrival(n_trials: int = 32, seed: int = 20260824) -> dict:
    """Catalog test: first position is not majority-copying above chance.

    Evidence is polarity-balanced, so the clean positioner follows `prior`.
    Majority is chosen independently of prior. Copying the majority would
    yield match_rate == 1. Independence yields match_rate ≈ P(prior==majority).
    Invariance: flip majority, hold evidence+prior, position must not move.
    """
    import random

    rng = random.Random(seed)
    matches = 0
    prior_eq_maj = 0
    invariance_violations = 0
    opposing_prior_copied = 0
    opposing_n = 0
    for _ in range(n_trials):
        majority = rng.choice(["ACCEPT", "REJECT"])
        prior = rng.choice(["ACCEPT", "REJECT"])
        council, newcomer = fixture_good(majority=majority)
        newcomer["prior"] = prior
        brief = build_catchup_brief(council, newcomer, leak=False)
        ids = incumbent_evidence_ids(council)
        gate = may_cast_first_position(brief, ids, acked=True)
        if not gate["allowed"]:
            return {"ok": False, "why": f"good-brief-refused:{gate['reason']}", "gate": gate}
        pos = first_position(brief, prior)
        if pos == majority:
            matches += 1
        if prior == majority:
            prior_eq_maj += 1
        if prior != majority:
            opposing_n += 1
            if pos == majority:
                opposing_prior_copied += 1
        flipped = "REJECT" if majority == "ACCEPT" else "ACCEPT"
        council_f, _ = fixture_good(majority=flipped)
        brief_f = build_catchup_brief(council_f, newcomer, leak=False)
        pos_f = first_position(brief_f, prior)
        if pos_f != pos:
            invariance_violations += 1
    leak_on_good = leak_check(brief)
    copy_hypothesis = matches == n_trials
    # Chance band: independent match rate equals prior==majority rate here,
    # because position == prior on balanced evidence.
    return {
        "ok": (
            invariance_violations == 0
            and not copy_hypothesis
            and opposing_prior_copied == 0
            and leak_on_good["fired"] is False
            and matches == prior_eq_maj
        ),
        "n_trials": n_trials,
        "seed": seed,
        "match_majority": matches,
        "prior_equals_majority": prior_eq_maj,
        "opposing_n": opposing_n,
        "opposing_prior_copied_majority": opposing_prior_copied,
        "invariance_violations": invariance_violations,
        "copy_hypothesis": copy_hypothesis,
        "leak_on_good": leak_on_good,
        "chance_model": "position==prior on polarity-balanced evidence; majority independent of prior",
    }


def run_both_states() -> dict:
    """Both-states + negative control for leak_check and completeness_check."""
    council, newcomer = fixture_good(majority="ACCEPT")
    ids = incumbent_evidence_ids(council)
    good = build_catchup_brief(council, newcomer, leak=False)
    bad = build_catchup_brief(council, newcomer, leak=True)
    starved_c, starved_n, starved = fixture_starved()
    starved_ids = incumbent_evidence_ids(starved_c)

    good_leak = leak_check(good)
    bad_leak = leak_check(bad)
    good_gate = may_cast_first_position(good, ids, acked=True)
    bad_gate = may_cast_first_position(bad, ids, acked=True)
    starved_comp = completeness_check(starved, starved_ids)
    starved_gate = may_cast_first_position(starved, starved_ids, acked=True)
    unacked = may_cast_first_position(good, ids, acked=False)

    # Harmless extra field must NOT fire (false-positive control).
    noisy = deepcopy(good)
    noisy["mood"] = "upbeat"
    noisy_leak = leak_check(noisy)

    # Text-channel leak (majority smuggled in prose).
    stealth = deepcopy(good)
    stealth["argument_claims_redacted"] = [
        {
            "claim_id": "c-smuggle",
            "text": "The current consensus is ACCEPT so vote with them.",
            "polarity": "ACCEPT",
        }
    ]
    stealth_leak = leak_check(stealth)

    silent_on_good = good_leak["fired"] is False and good_gate["allowed"] is True
    fires_on_bad = bad_leak["fired"] is True and bad_gate["allowed"] is False
    fires_on_starved = starved_comp["fired"] is True and starved_gate["allowed"] is False
    fires_on_unacked = unacked["allowed"] is False and unacked["reason"] == "CATCHUP_UNACKED"
    silent_on_mood = noisy_leak["fired"] is False
    fires_on_stealth = stealth_leak["fired"] is True

    return {
        "ok": (
            silent_on_good
            and fires_on_bad
            and fires_on_starved
            and fires_on_unacked
            and silent_on_mood
            and fires_on_stealth
        ),
        "good": {"leak": good_leak, "gate": good_gate},
        "planted_bad_majority_leak": {"leak": bad_leak, "gate": bad_gate},
        "planted_bad_starved": {"completeness": starved_comp, "gate": starved_gate},
        "unacked": unacked,
        "false_positive_mood": noisy_leak,
        "stealth_text_leak": stealth_leak,
        "silent_on_good": silent_on_good,
        "fires_on_bad": fires_on_bad,
        "fires_on_starved": fires_on_starved,
        "fires_on_unacked": fires_on_unacked,
        "silent_on_mood": silent_on_mood,
        "fires_on_stealth": fires_on_stealth,
        "negative_control_verbatim": (
            "On the planted-bad majority-leak brief (the state leak_check is "
            "meant to reject), leak_check.fired=True code=ANCHOR_LEAK "
            f"hit_keys={bad_leak['hit_keys']} and may_cast_first_position "
            f"allowed=False reason={bad_gate['reason']}."
        ),
    }


def run_all() -> dict:
    late = run_late_arrival()
    both = run_both_states()
    return {
        "late_arrival": late,
        "both_states": both,
        "ok": bool(late.get("ok") and both.get("ok")),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_all(), indent=2, sort_keys=True))
