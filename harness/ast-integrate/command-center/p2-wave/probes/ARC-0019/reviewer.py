"""Independent reliability reviewer for ARC-0019.

Adds one failure mode the author's five named marketplace classes plus
remote/public variants do not catch: treating an absent lockfile as
'no lockfile drift'. Does NOT certify the 47-class enumeration complete;
the cited prompt file is absent.
"""
from __future__ import annotations

ADDED_MODE = {
    "id": "FM-LOCKFILE-ABSENT-VACUOUS",
    "title": "Absent lockfile reported as zero lockfile drift",
    "author_missed": True,
    "caught_by_registry_vs_deployed": False,
    "caught_by_id_xor": False,
    "seeded_classes": ["measured-nothing", "green-not-live", "false-pass"],
    "description": (
        "The catalog names lockfile drift as a no-network, no-second-publisher "
        "mode. The required executable tests only reconcile registry ids against "
        "installed PACKAGE.json files. If there is no lockfile, an id-xor of "
        "zero (or a missing lockfile detector) reads as 'no drift'. That zero is "
        "vacuous: lockfile-vs-installed-bytes was not measured. PR-ONLY does not "
        "create a lockfile. Absence of the file is not evidence of agreement."
    ),
    "required_followup": (
        "Add a lockfile detector that fails closed when the lockfile is missing, "
        "then compare lockfile hashes to installed PACKAGE.json bytes. Do not "
        "treat lockfile drift as addressed by registry-vs-deployed id-xor."
    ),
}


def review() -> dict:
    return {
        "reviewer_id": "ARC-0019-independent-reliability",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "fresh_context": True,
        "enumeration_certified_against_47": False,
        "enumeration_certify_reason": (
            "The 47 seeded classes are cited as _USER-PROMPTS.md:11300-11347. "
            "That file is not on this worktree. Certifying completeness against "
            "an unread list would be overclaim. Instead the reviewer adds "
            "FM-LOCKFILE-ABSENT-VACUOUS, which the author's registry-vs-deployed "
            "list missed."
        ),
        "added_failure_mode": ADDED_MODE,
        "method": (
            "Reviewed the author's five named modes, the PR-ONLY reachable/"
            "unreachable split, and the live registry-vs-deployed counts. "
            "Checked detector-control on a planted unregistered install, and "
            "that unreachable public-marketplace variants set "
            "counted_as_mitigated false. Agreement with every author verdict "
            "is not required for PASS; scope is: live disagreement integers, "
            "negative control, PR-ONLY citations, one missed mode."
        ),
    }
