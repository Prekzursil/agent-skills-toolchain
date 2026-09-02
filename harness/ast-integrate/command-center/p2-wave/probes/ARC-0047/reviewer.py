"""Independent reliability reviewer for ARC-0047.

Adds one failure mode the author's four catalog classes do not catch:
a gate whose except-path returns PASS. Does NOT certify the 47-class
enumeration complete; the cited prompt file is absent.
"""
from __future__ import annotations

ADDED_MODE = {
    "id": "FM-EXCEPT-PASS",
    "title": "Evaluator exception returns PASS",
    "author_missed": True,
    "caught_by_text_vs_verb": False,
    "caught_by_require_flag": False,
    "caught_by_silent_both": False,
    "caught_by_absent_pass": False,
    "seeded_classes": ["fail-open-control", "detector-failure", "green-not-live"],
    "description": (
        "The four catalog classes assume the gate function returns a decision. "
        "If evaluation raises (bad fixture, missing import, JSON decode of the "
        "policy file) and the caller treats that exception as allow/pass, the "
        "gate is silent on a broken input without matching TEXT, skipping a "
        "require-flag, always-returning-pass, or normalizing a missing *input* "
        "field. It is a fifth fail-open: missing *evaluator*, not missing input."
    ),
    "required_followup": (
        "except around a security gate must FAIL-CLOSE. Both-states for this "
        "class is: plant an eval error on a known-broken event and assert FIRE; "
        "restore a clean evaluator and assert the good event is silent."
    ),
}


def review() -> dict:
    return {
        "reviewer_id": "ARC-0047-independent-reliability",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "fresh_context": True,
        "enumeration_certified_against_47": False,
        "enumeration_certify_reason": (
            "The 47 seeded classes are cited as _USER-PROMPTS.md:11300-11347. "
            "That file is not on this worktree. Certifying completeness against "
            "an unread list would be overclaim. Instead the reviewer adds "
            "FM-EXCEPT-PASS, which the author's four catalog classes missed."
        ),
        "added_failure_mode": ADDED_MODE,
        "method": (
            "Re-ran the both-states audit table. Checked that every row records "
            "broken and good outcomes, that silent-in-both is MEASURING-NOTHING, "
            "that the text-matching gates fire on mention while the verb gate "
            "does not, and that A7 DESIGN.json is recorded absent rather than "
            "invented. Agreement with which live gate is 'the' choke point is "
            "not required for PASS; scope is: both-states table, use-vs-mention, "
            "four named fail-open classes, one missed mode."
        ),
    }
