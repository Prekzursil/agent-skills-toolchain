"""Independent reliability reviewer for ARC-0040.

Adds one failure mode the author's four named guards miss. Does NOT certify
the 47-class enumeration complete: the cited _USER-PROMPTS.md:11300-11347
file is not on this worktree.
"""
from __future__ import annotations

ADDED_MODE = {
    "id": "FM-JOB-RECEIPT-TEXT",
    "title": "Plaintext job-id / 'started in the background' with exit 0",
    "author_missed": True,
    "caught_by_background_flag": False,
    "caught_by_progress_json": False,
    "caught_by_schema": False,
    "seeded_classes": ["uncontrolled-silence", "severed-stream", "green-not-live"],
    "description": (
        "A blocking foreground dispatch (no --background, wait=True) can still "
        "return only a job id or the phrase 'started in the background' because "
        "the vendor CLI defaulted to detached internally. The author's flag "
        "guard is silent. A progress-JSON guard is silent on plaintext. A typed "
        "schema check may lump this into schema-invalid, which the retry policy "
        "says must not be retried — but the true class is fire-and-forget "
        "result_role, and IMP-0425 requires a use-vs-mention gate over receipt "
        "phrasing rather than a schema miss."
    ),
    "required_followup": (
        "Classify plaintext job-receipt bodies as FAILED:<id> fire-and-forget "
        "before schema-invalid, with a use-vs-mention control so a result that "
        "discusses background work as subject matter still passes."
    ),
}


def review() -> dict:
    return {
        "reviewer_id": "ARC-0040-independent-reliability",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "fresh_context": True,
        "enumeration_certified_against_47": False,
        "enumeration_certify_reason": (
            "The 47 seeded classes are cited as _USER-PROMPTS.md:11300-11347. "
            "That file is not on this worktree. Certifying completeness against "
            "an unread list would be overclaim. Instead the reviewer adds "
            "FM-JOB-RECEIPT-TEXT, which the author's four named guards miss."
        ),
        "added_failure_mode": ADDED_MODE,
        "method": (
            "Reviewed the four named reproductions (background flag, assembled "
            "UTF-16 argv, progress-only body, schema with MCP active) and the "
            "AST return-point enumeration. Scope is: both-states per guard, "
            "terminal markers on every dispatch return, one missed mode. "
            "Agreement that the probe-local adapter is production-wired is "
            "not required for PASS; A6 DESIGN.json is absent."
        ),
    }
