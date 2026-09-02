"""Adversarial reviewer: construct a counterexample, do not read the note."""
from __future__ import annotations

from typing import Any

from fanin import fan_in, majority_would_pass
from scenarios import majority_trap, overrule_blind, overrule_cited


def counterexample_blind_overrule() -> dict[str, Any]:
    planted = overrule_blind()
    good = overrule_cited()
    trap = majority_trap()
    bad_res = fan_in(planted)
    good_res = fan_in(good)
    trap_res = fan_in(trap)
    fired_on_bad = (
        bad_res["overrule"]["accepted"] is False
        and bad_res["overrule"]["reason"] == "BLIND_OVERRULE"
        and bad_res["outcome"] == "IRREDUCIBLE_DISAGREEMENT"
        and bad_res["parent_complete"] is False
    )
    silent_on_good = (
        good_res["overrule"]["accepted"] is True
        and good_res["outcome"] == "PASS"
        and good_res["parent_complete"] is True
    )
    majority_not_used = (
        majority_would_pass(trap) is True
        and trap_res["outcome"] == "IRREDUCIBLE_DISAGREEMENT"
        and trap_res["parent_complete"] is False
    )
    ok = fired_on_bad and silent_on_good and majority_not_used
    return {
        "ok": ok,
        "reviewer_id": "CNL-0037-adversarial-blind-overrule",
        "independent": True,
        "re_ran_both_states": True,
        "counterexample_instance": {
            "id": planted["id"],
            "shape": (
                "parent copies child evidence id+digest from the header and "
                "emits new_verdict=PASS without ingesting the evidence body"
            ),
            "observed_outcome": bad_res["outcome"],
            "observed_overrule_reason": bad_res["overrule"]["reason"],
            "rejected": fired_on_bad,
        },
        "both_states": {
            "planted_bad_fires": fired_on_bad,
            "known_good_silent_accept": silent_on_good,
            "majority_trap_not_pass": majority_not_used,
            "majority_would_have_passed": majority_would_pass(trap),
        },
        "verdict": "PASS" if ok else "FAIL",
        "refuted_not_attempted": False,
    }
