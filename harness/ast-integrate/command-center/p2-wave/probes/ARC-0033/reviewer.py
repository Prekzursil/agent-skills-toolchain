"""Independent reliability reviewer for ARC-0033.

Adds FM-SENTINEL-ON-PARTIAL, the inverse of the author's FC-11313 mode.
Does not certify the 47 seeded classes complete: the cited prompt file
is not on this worktree.
"""
from __future__ import annotations

ADDED_MODE = {
    "id": "FM-SENTINEL-ON-PARTIAL",
    "title": "Sentinel present on a partial artifact",
    "author_missed": True,
    "seeded_classes": [
        "partial-artifact",
        "false-pass",
        "two-completion-predicates-disagree",
    ],
    "description": (
        "The author converted 'partial artifact without sentinel' into "
        "artifact.observe.bytes>0 AND sentinel_present==false. The more "
        "dangerous inverse is a completion sentinel on a file that fails "
        "the completion predicate (bytes too small, schema invalid, or "
        "self-declared BLOCKED). That manufactures a pass. Catalog units "
        "AUD-0011 / TST-0113 already name this as the worse direction of "
        "FC-11313, and FC-11314 is the two-predicate disagreement class. "
        "The author's five-mode list does not include it."
    ),
    "ledger_record": "artifact.observe.{sentinel_present,completion_predicate}",
    "alert_predicate": (
        "FIRE iff sentinel_present is true AND completion_predicate is not true"
    ),
    "required_followup": (
        "Gate SUCCESS on (sentinel present AND completion predicate true), "
        "never on the sentinel token alone."
    ),
}


def review() -> dict:
    return {
        "reviewer_id": "ARC-0033-independent-reliability",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "fresh_context": True,
        "enumeration_certified_against_47": False,
        "enumeration_certify_reason": (
            "The 47 seeded classes are cited as _USER-PROMPTS.md:11301-11347. "
            "That file is not on this worktree. Certifying completeness against "
            "an unread list would be overclaim. The reviewer adds "
            "FM-SENTINEL-ON-PARTIAL, which the author's five named silences "
            "missed (the inverse of FC-11313)."
        ),
        "added_failure_mode": ADDED_MODE,
        "method": (
            "Checked that each of the five catalog-named silences has a ledger "
            "field and a both-states pair, that stall predicates do not read "
            "mtime, and that A5 DESIGN.json is absent so field names are a "
            "proposed contract not a dossier quote. Agreement with every "
            "author CONFIRMED row is not required; scope is: five named "
            "modes, both-states, anti-mtime, one missed mode."
        ),
    }
