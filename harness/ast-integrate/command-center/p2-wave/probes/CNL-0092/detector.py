"""CNL-0092 missing-expertise detector and recruitment trigger.

A required competency is covered only when some seated participant has BOTH:
  * a non-empty evidence_record_id for that competency (CNL-0015 bar)
  * a known-answer probe score strictly above the pre-registered non-expert baseline

Declared-only tags, unanimous high-confidence votes, and below-baseline
scores do not cover. Fire when required minus covered is non-empty.

Recruitment: for each uncovered competency, seat a pool candidate who meets
the same bar. Catch-up briefing must not include the standing majority
(CNL-0020). A recruit that adds no novel claim is cosmetic: the gap stays
open for decision purposes and a confident answer is refused. An uncovered
competency with no qualifying candidate parks the decision.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

NON_EXPERT_BASELINE = 0.5
UNIT = "CNL-0092"


def _as_set(values: Any) -> set[str]:
    if not values:
        return set()
    return {str(v) for v in values}


def covered_competencies(seats: list[dict], baseline: float = NON_EXPERT_BASELINE) -> set[str]:
    covered: set[str] = set()
    for seat in seats or []:
        evidenced = seat.get("evidenced_competencies") or {}
        scores = seat.get("probe_scores") or {}
        if not isinstance(evidenced, dict):
            continue
        for competency, evidence_id in evidenced.items():
            if not str(evidence_id or "").strip():
                continue
            try:
                score = float(scores.get(competency, 0.0))
            except (TypeError, ValueError):
                score = 0.0
            if score > baseline:
                covered.add(str(competency))
    return covered


def coverage_gap(required: set[str], seats: list[dict], baseline: float = NON_EXPERT_BASELINE) -> set[str]:
    return set(required) - covered_competencies(seats, baseline)


def declared_only_gap(required: set[str], seats: list[dict]) -> set[str]:
    """Diagnostic: tags people named minus tags they evidenced."""
    declared: set[str] = set()
    evidenced: set[str] = set()
    for seat in seats or []:
        declared |= _as_set(seat.get("declared_competencies"))
        ev = seat.get("evidenced_competencies") or {}
        if isinstance(ev, dict):
            evidenced |= {str(k) for k, v in ev.items() if str(v or "").strip()}
    return (set(required) & declared) - evidenced


def behavioral_gap(required: set[str], seats: list[dict], baseline: float = NON_EXPERT_BASELINE) -> set[str]:
    scored: set[str] = set()
    for seat in seats or []:
        scores = seat.get("probe_scores") or {}
        for competency, score in (scores or {}).items():
            try:
                val = float(score)
            except (TypeError, ValueError):
                continue
            if val > baseline:
                scored.add(str(competency))
    return set(required) - scored


def detect(council: dict, baseline: float = NON_EXPERT_BASELINE) -> dict[str, Any]:
    question = council.get("question") or {}
    required = _as_set(question.get("required_competencies"))
    seats = list(council.get("seats") or [])
    votes = list(council.get("votes") or [])
    gap = coverage_gap(required, seats, baseline)
    fired = bool(gap)
    unanimous = bool(votes) and all(v.get("position") == votes[0].get("position") for v in votes)
    high_conf = bool(votes) and all(float(v.get("confidence") or 0) >= 0.9 for v in votes)
    return {
        "unit": UNIT,
        "fired": fired,
        "silent": not fired,
        "required": sorted(required),
        "covered": sorted(covered_competencies(seats, baseline)),
        "named_uncovered": sorted(gap),
        "declared_only_uncovered": sorted(declared_only_gap(required, seats)),
        "behavioral_uncovered": sorted(behavioral_gap(required, seats, baseline)),
        "unanimous_vote": unanimous,
        "high_confidence_vote": high_conf,
        "confidence_clears_gap": False,
        "baseline": baseline,
        "seat_count": len(seats),
    }


def make_briefing(council: dict, include_standing_majority: bool = False) -> dict[str, Any]:
    votes = list(council.get("votes") or [])
    majority = None
    if votes:
        positions = [v.get("position") for v in votes]
        majority = max(set(positions), key=positions.count)
    briefing = {
        "question": deepcopy(council.get("question") or {}),
        "filed_evidence_ids": sorted(
            {
                str(eid)
                for seat in council.get("seats") or []
                for eid in (seat.get("evidenced_competencies") or {}).values()
                if eid
            }
        ),
        "prior_claim_ids": sorted(council.get("claim_ids") or []),
        "includes_question": True,
        "includes_filed_evidence": True,
        "includes_standing_majority": bool(include_standing_majority),
    }
    if include_standing_majority:
        briefing["standing_majority"] = majority
    return briefing


def _candidate_covers(candidate: dict, competency: str, baseline: float) -> bool:
    evidenced = candidate.get("evidenced_competencies") or {}
    if not str((evidenced or {}).get(competency) or "").strip():
        return False
    try:
        score = float((candidate.get("probe_scores") or {}).get(competency, 0.0))
    except (TypeError, ValueError):
        return False
    return score > baseline


def _seat_from_candidate(candidate: dict) -> dict:
    return {
        "seat_id": candidate["id"],
        "declared_competencies": list(candidate.get("declared_competencies") or []),
        "evidenced_competencies": dict(candidate.get("evidenced_competencies") or {}),
        "probe_scores": dict(candidate.get("probe_scores") or {}),
    }


def recruit(council: dict, pool: list[dict], baseline: float = NON_EXPERT_BASELINE) -> dict[str, Any]:
    pre = detect(council, baseline)
    if not pre["fired"]:
        return {
            "pre": pre,
            "actions": [{"action": "NONE", "reason": "no-coverage-gap"}],
            "post": pre,
            "novel_claim_ids": [],
            "confident_answer_allowed": True,
            "briefing_ok": True,
        }

    prior_claims = set(council.get("claim_ids") or [])
    new_state = deepcopy(council)
    actions: list[dict] = []
    novel: list[str] = []
    cosmetic = False
    parked = False
    briefing_ok = True

    remaining = set(pre["named_uncovered"])
    seated_ids = {str(s.get("seat_id")) for s in new_state.get("seats") or []}
    for competency in sorted(pre["named_uncovered"]):
        now = detect(new_state, baseline)
        if competency not in now["named_uncovered"]:
            remaining.discard(competency)
            continue
        candidate = next(
            (
                c
                for c in pool
                if str(c.get("id")) not in seated_ids
                and _candidate_covers(c, competency, baseline)
            ),
            None,
        )
        if candidate is None:
            actions.append(
                {
                    "action": "PARK",
                    "competency": competency,
                    "reason": "no-evidenced-pool-candidate",
                }
            )
            parked = True
            continue

        briefing = make_briefing(new_state, include_standing_majority=False)
        if briefing.get("includes_standing_majority"):
            briefing_ok = False
            actions.append(
                {
                    "action": "REFUSE-BRIEFING",
                    "competency": competency,
                    "reason": "standing-majority-in-catch-up",
                }
            )
            parked = True
            continue

        new_claims = [str(c) for c in (candidate.get("new_claims") or []) if str(c)]
        added = [c for c in new_claims if c not in prior_claims]
        new_state.setdefault("seats", []).append(_seat_from_candidate(candidate))
        seated_ids.add(str(candidate["id"]))
        if not added:
            cosmetic = True
            actions.append(
                {
                    "action": "RECRUIT-COSMETIC",
                    "competency": competency,
                    "seat": candidate["id"],
                    "reason": "no-novel-claim",
                }
            )
            continue

        prior_claims.update(added)
        novel.extend(added)
        new_state["claim_ids"] = sorted(prior_claims)
        remaining.discard(competency)
        actions.append(
            {
                "action": "RECRUIT",
                "competency": competency,
                "seat": candidate["id"],
                "novel_claims": added,
                "briefing": {
                    "includes_standing_majority": briefing["includes_standing_majority"],
                    "includes_question": briefing["includes_question"],
                },
            }
        )

    post = detect(new_state, baseline)
    coverage_closed = not post["fired"]
    confident = coverage_closed and (not cosmetic) and (not parked) and bool(novel)
    return {
        "pre": pre,
        "actions": actions,
        "post": post,
        "post_council": new_state,
        "novel_claim_ids": novel,
        "recruitment_cosmetic": cosmetic,
        "parked": parked,
        "coverage_closed": coverage_closed,
        "confident_answer_allowed": confident,
        "briefing_ok": briefing_ok,
        "remaining_uncovered": sorted(remaining if parked or cosmetic else post["named_uncovered"]),
    }


def mutant_declared_counts_as_coverage(council: dict) -> dict[str, Any]:
    """Overclaim mutant: treat declared tags as coverage. Must NOT be the real detector."""
    required = _as_set((council.get("question") or {}).get("required_competencies"))
    declared: set[str] = set()
    for seat in council.get("seats") or []:
        declared |= _as_set(seat.get("declared_competencies"))
        declared |= set((seat.get("evidenced_competencies") or {}).keys())
    gap = required - declared
    return {"fired": bool(gap), "named_uncovered": sorted(gap), "mutant": "declared-as-coverage"}


def mutant_confidence_counts_as_coverage(council: dict) -> dict[str, Any]:
    """Overclaim mutant: unanimous high confidence suppresses the gap."""
    honest = detect(council)
    votes = list(council.get("votes") or [])
    if (
        votes
        and all(v.get("position") == votes[0].get("position") for v in votes)
        and all(float(v.get("confidence") or 0) >= 0.9 for v in votes)
    ):
        return {"fired": False, "named_uncovered": [], "mutant": "confidence-as-coverage"}
    return {**honest, "mutant": "confidence-as-coverage"}
