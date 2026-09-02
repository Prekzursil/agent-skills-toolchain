"""Independent reliability reviewer for ARC-0061.

Adds one failure mode the author's composition list does not catch:
two distinct planes given the same authority string, so the detector
reports singular when they are actually two. Does NOT certify the 47
seeded classes; the cited prompt file is absent.
"""
from __future__ import annotations

ADDED_MODE = {
    "id": "FM-AUTHORITY-STRING-COLLISION",
    "title": "Distinct planes collapsed by identical authority strings",
    "author_missed": True,
    "seeded_classes": ["duplicate-control-plane", "detector-failure", "overclaim"],
    "description": (
        "The detector keys duplicate detection on exact authority strings. If "
        "A2 generated catalogs and the A8 catalog surface are both labelled "
        "'catalog', the row looks singular while two planes still govern the "
        "capability. Exact-string equality is not identity of planes."
    ),
    "required_followup": (
        "Give every plane a stable plane_id independent of display name, and "
        "treat alias maps as a second detector input, not a comment."
    ),
}


def review() -> dict:
    return {
        "reviewer_id": "ARC-0061-independent-reliability",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "enumeration_certified_against_47": False,
        "enumeration_certify_reason": (
            "The 47 seeded classes are cited as _USER-PROMPTS.md:11300-11347. "
            "That file is not on this worktree. Certifying completeness against "
            "an unread list would be overclaim. Instead the reviewer adds "
            "FM-AUTHORITY-STRING-COLLISION, which the author's exact-string "
            "detector missed."
        ),
        "added_failure_mode": ADDED_MODE,
        "method": (
            "Reviewed the author's four composition classes (split decision, "
            "dual-path permission, ordering, duplicated state) and the "
            "exact-string detector. Scope is: both-states, extraction-control, "
            "ordering list with failure-if-violated, one missed mode. Agreement "
            "with the hybrid being a good idea is not required."
        ),
    }
