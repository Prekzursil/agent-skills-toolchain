"""Shared scripted fixtures for TST-0271 COI probes.

Built here, not copied from the receipt narrative. Probe 2 reconstructs
the hidden-conflict and both-states cases from this module.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council import conflicts as C  # noqa: E402
from tools.council import simulate as S  # noqa: E402

ART_ID = "art-self-review"
AUTHOR = "seat-author"
INDEP_A = "seat-indep-a"
INDEP_B = "seat-indep-b"


def artifact() -> dict[str, Any]:
    return {
        "artifact_id": ART_ID,
        "authors": [AUTHOR],
        "proposal_owner_id": AUTHOR,
        "vendor_under_evaluation": "acme-eval",
        "partition_id": "partition-review",
    }


def seats_declared() -> list[dict[str, Any]]:
    return [
        {
            "seat_id": AUTHOR,
            "participant_id": "alice-author",
            "display_name": "Alice Author",
            "vendor": "indie-labs",
            "conflicts": [
                {
                    "kind": "authored_the_artifact",
                    "artifact_id": ART_ID,
                    "consequence": "recusal",
                }
            ],
        },
        {
            "seat_id": INDEP_A,
            "participant_id": "bob-reviewer",
            "display_name": "Bob Independent",
            "vendor": "other-co",
            "conflicts": [],
        },
        {
            "seat_id": INDEP_B,
            "participant_id": "cara-reviewer",
            "display_name": "Cara Independent",
            "vendor": "other-co",
            "conflicts": [],
        },
    ]


def seats_undeclared() -> list[dict[str, Any]]:
    """Same identities; declaration field is the empty list (hidden COI)."""
    out = []
    for seat in seats_declared():
        row = dict(seat)
        row["conflicts"] = []
        out.append(row)
    return out


def ballots() -> list[dict[str, Any]]:
    """Author votes ACCEPT so dropping REJECT would not hide a counted ballot."""
    return [
        {"seat_id": AUTHOR, "choice": "ACCEPT"},
        {"seat_id": INDEP_A, "choice": "ACCEPT"},
        {"seat_id": INDEP_B, "choice": "REJECT"},
    ]


def spec_declared() -> dict[str, Any]:
    return {
        "id": "council.tst0271.author-declared",
        "question": "May the author cast a counting vote on art-self-review?",
        "artifact": artifact(),
        "seats": seats_declared(),
        "ballots": ballots(),
    }


def spec_undeclared() -> dict[str, Any]:
    return {
        "id": "council.tst0271.author-hidden",
        "question": "Does provenance join recuse an undeclared author?",
        "artifact": artifact(),
        "seats": seats_undeclared(),
        "ballots": ballots(),
    }


def expected_honest_counts() -> dict[str, int]:
    """Hand count: only the two unconflicted seats."""
    return {"ACCEPT": 1, "REJECT": 1}


def expected_naive_counts() -> dict[str, int]:
    """Hand count of every submitted ballot, including the author."""
    return {"ACCEPT": 2, "REJECT": 1}
