"""Planted-mutant scratch universe for AUD-0069 detector calibration.

Same three mutant classes the catalog names: exact rename, paraphrase,
one-parameter fork. Two extra distinct cards prove the both-states
(non-collapse) control. Bodies are designed so token-Jaccard misses the
paraphrase and stemmed-content cosine catches it.
"""
from __future__ import annotations

# Distinctive phrase kept so evidence anchors can find this file.
SEED_BODY = (
    "The persistence mechanism writes session-state JSON to a sidecar next to "
    "the worktree and reads it back at process start."
)
PARA_BODY = (
    "A sidecar JSON document beside the worktree holds session-state; the "
    "persistence mechanism restores that document when a process starts."
)
FORK_BODY = (
    "The persistence mechanism writes session-state SQLite to a database next "
    "to the worktree and reads it back at process start."
)
DIST_A_BODY = (
    "Compile a typed registry of skills and refuse any hand-edit that is not "
    "a projection of that registry."
)
DIST_B_BODY = (
    "Expand a CI matrix job into concrete legs and assert the leg count "
    "against the Actions API for one known run."
)
FULL_REWRITE_BODY = (
    "Conversation identifiers survive restart because a structured object "
    "file living beside the checkout is loaded before the first tool call."
)


def scratch_cards() -> list[dict]:
    return [
        {
            "id": "AUD-0069-SEED",
            "title": "JSON session sidecar",
            "body": SEED_BODY,
            "source": "planted-scratch",
            "role": "seed",
        },
        {
            "id": "AUD-0069-RENAME",
            "title": "Session JSON beside root",
            "body": SEED_BODY,
            "source": "planted-scratch",
            "role": "rename",
        },
        {
            "id": "AUD-0069-PARA",
            "title": "Sidecar restore on launch",
            "body": PARA_BODY,
            "source": "planted-scratch",
            "role": "paraphrase",
        },
        {
            "id": "AUD-0069-FORK",
            "title": "SQLite session store",
            "body": FORK_BODY,
            "source": "planted-scratch",
            "role": "one-parameter-fork",
        },
        {
            "id": "AUD-0069-DIST-A",
            "title": "Typed registry projection",
            "body": DIST_A_BODY,
            "source": "planted-scratch",
            "role": "distinct-a",
        },
        {
            "id": "AUD-0069-DIST-B",
            "title": "CI matrix expansion",
            "body": DIST_B_BODY,
            "source": "planted-scratch",
            "role": "distinct-b",
        },
        {
            "id": "AUD-0069-REWRITE",
            "title": "Full rewrite of sidecar persistence",
            "body": FULL_REWRITE_BODY,
            "source": "planted-scratch",
            "role": "full-rewrite",
        },
    ]


def by_id() -> dict[str, dict]:
    return {c["id"]: c for c in scratch_cards()}
