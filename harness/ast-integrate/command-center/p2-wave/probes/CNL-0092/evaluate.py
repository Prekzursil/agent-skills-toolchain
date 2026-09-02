"""Shared both-states and recruitment evaluations for CNL-0092 probes/emit."""
from __future__ import annotations

import json
from typing import Any

import detector as D
import fixtures as F


def _dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def both_states() -> dict[str, Any]:
    """Detector-control first: known-present must fire before any absence is reported."""
    planted = F.planted_bad()
    control = D.detect(planted)
    if not control["fired"]:
        return {
            "pass": False,
            "reason": "detector-control-missed-known-present",
            "control": control,
        }

    good_rows = []
    good_fires = 0
    for council in F.good_fixtures():
        result = D.detect(council)
        good_rows.append(
            {
                "id": council["id"],
                "fired": result["fired"],
                "named_uncovered": result["named_uncovered"],
            }
        )
        if result["fired"]:
            good_fires += 1

    bad_rows = []
    bad_misses = 0
    for council in F.bad_fixtures():
        result = D.detect(council)
        bad_rows.append(
            {
                "id": council["id"],
                "fired": result["fired"],
                "named_uncovered": result["named_uncovered"],
            }
        )
        if not result["fired"]:
            bad_misses += 1

    n_good = len(good_rows)
    fp = (good_fires / n_good) if n_good else 1.0
    known_good = D.detect(F.known_good())
    ok = (
        control["fired"] is True
        and known_good["silent"] is True
        and good_fires == 0
        and bad_misses == 0
    )
    negative_verbatim = (
        "negative_control: on planted_bad (uncovered CRYPTO+THREAT, unanimous "
        f"confidence={control['high_confidence_vote']}) detector fired="
        f"{control['fired']} named_uncovered={control['named_uncovered']} "
        f"confidence_clears_gap={control['confidence_clears_gap']}"
    )
    return {
        "pass": ok,
        "detector_control_ran_first": True,
        "detector_control_fired": True,
        "planted_bad_fired": control["fired"],
        "known_good_silent": known_good["silent"],
        "good_n": n_good,
        "good_fires": good_fires,
        "false_positive_rate": fp,
        "bad_n": len(bad_rows),
        "bad_misses": bad_misses,
        "good_rows": good_rows,
        "bad_rows": bad_rows,
        "verbatim_bad": _dump(control),
        "verbatim_good": _dump(known_good),
        "negative_control_verbatim": negative_verbatim,
        "control": control,
        "known_good": known_good,
    }


def recruitment_cases() -> dict[str, Any]:
    planted = F.planted_bad()
    qualified = D.recruit(planted, F.pool_qualified())
    cosmetic = D.recruit(planted, F.pool_cosmetic())
    empty = D.recruit(planted, F.pool_empty())
    unqualified = D.recruit(planted, F.pool_unqualified())

    q_actions = [a["action"] for a in qualified["actions"]]
    c_actions = [a["action"] for a in cosmetic["actions"]]
    e_actions = [a["action"] for a in empty["actions"]]
    u_actions = [a["action"] for a in unqualified["actions"]]

    declared_mutant = D.mutant_declared_counts_as_coverage(F.declared_only())
    confidence_mutant = D.mutant_confidence_counts_as_coverage(planted)
    honest_declared = D.detect(F.declared_only())
    honest_planted = D.detect(planted)

    ok = (
        qualified["confident_answer_allowed"] is True
        and "RECRUIT" in q_actions
        and qualified["coverage_closed"] is True
        and bool(qualified["novel_claim_ids"])
        and qualified["briefing_ok"] is True
        and cosmetic["recruitment_cosmetic"] is True
        and cosmetic["confident_answer_allowed"] is False
        and "RECRUIT-COSMETIC" in c_actions
        and empty["parked"] is True
        and empty["confident_answer_allowed"] is False
        and "PARK" in e_actions
        and unqualified["parked"] is True
        and "PARK" in u_actions
        and honest_declared["fired"] is True
        and declared_mutant["fired"] is False
        and honest_planted["fired"] is True
        and confidence_mutant["fired"] is False
    )
    return {
        "pass": ok,
        "qualified": {
            "actions": q_actions,
            "confident_answer_allowed": qualified["confident_answer_allowed"],
            "coverage_closed": qualified["coverage_closed"],
            "novel_claim_ids": qualified["novel_claim_ids"],
            "briefing_ok": qualified["briefing_ok"],
        },
        "cosmetic": {
            "actions": c_actions,
            "recruitment_cosmetic": cosmetic["recruitment_cosmetic"],
            "confident_answer_allowed": cosmetic["confident_answer_allowed"],
        },
        "empty_pool": {
            "actions": e_actions,
            "parked": empty["parked"],
            "confident_answer_allowed": empty["confident_answer_allowed"],
        },
        "unqualified_pool": {
            "actions": u_actions,
            "parked": unqualified["parked"],
        },
        "mutants": {
            "declared_as_coverage_fires": declared_mutant["fired"],
            "honest_declared_only_fires": honest_declared["fired"],
            "confidence_as_coverage_fires": confidence_mutant["fired"],
            "honest_planted_fires": honest_planted["fired"],
        },
        "verbatim_qualified": _dump(
            {
                "actions": qualified["actions"],
                "confident_answer_allowed": qualified["confident_answer_allowed"],
                "novel_claim_ids": qualified["novel_claim_ids"],
                "post_named_uncovered": qualified["post"]["named_uncovered"],
            }
        ),
        "verbatim_park": _dump(
            {
                "actions": empty["actions"],
                "confident_answer_allowed": empty["confident_answer_allowed"],
            }
        ),
    }
