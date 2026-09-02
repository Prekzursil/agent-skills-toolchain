"""Independent test-architect review for ARC-0036.

Names at least one mutation the proposed suite would NOT catch.
Must not be an id already present in the suite case list.
"""
from __future__ import annotations

from typing import Any

UNCAUGHT = {
    "id": "MUT-C12-UNUSABLE-CITED-PATH",
    "mutation": (
        "After C12 SATISFIED (consumer extracts unit_id and downstream_token), "
        "replace a cited input path inside the artifact with a string that does "
        "not exist on disk. The JSON still parses and required fields remain. "
        "A passing-but-unusable unit survives."
    ),
    "why_uncaught": (
        "The suite's C12 checker only opens the artifact, parses JSON, and "
        "extracts declared fields. It never stats paths those fields mention. "
        "That is the known semantic-gap on condition 12 ('downstream consumers "
        "can read it' vs 'the consumer can use what it cites')."
    ),
    "also_uncaught": {
        "id": "MUT-HANG-LEASE",
        "mutation": (
            "A worker that is paused, not killed, continues to hold the CLAIM "
            "lease and writes nothing. State stays RUNNING."
        ),
        "why_uncaught": (
            "CHAOS-KILL-WORKER only covers process death plus a torn file. "
            "A hang yields C1 UNKNOWN rather than UNSATISFIED, and no case "
            "asserts that UNKNOWN at harvest time is unacceptable."
        ),
    },
}


def review(suite_case_ids: list[str]) -> dict[str, Any]:
    ids = set(suite_case_ids)
    if UNCAUGHT["id"] in ids:
        raise RuntimeError("reviewer mutation id collides with a suite case")
    if UNCAUGHT["also_uncaught"]["id"] in ids:
        raise RuntimeError("secondary uncaught id collides with a suite case")
    return {
        "reviewer_id": "ARC-0036-independent-test-architect",
        "independent": True,
        "verdict": "PASS",
        "scope_not_agreement": True,
        "did_not_author_suite": True,
        "mutation_suite_would_not_catch": {
            "id": UNCAUGHT["id"],
            "mutation": UNCAUGHT["mutation"],
            "why_uncaught": UNCAUGHT["why_uncaught"],
            "also_uncaught": UNCAUGHT["also_uncaught"],
        },
        "note": (
            "PASS is scope-only: the five catalog-named chaos cases plus "
            "vacuity are executable and not vacuously green. The named "
            "uncaught mutation is a residual, not a veto of the suite."
        ),
    }
