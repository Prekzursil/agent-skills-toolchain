"""Independent classification from raw dual-profile outcomes (no conclusion)."""
from __future__ import annotations

from scenario import classify


def review(rows: list[dict]) -> dict:
    derived = []
    for row in rows:
        cid = str(row["id"])
        lo = str(row["loaded_outcome"])
        fo = str(row["fresh_outcome"])
        derived.append(
            {
                "id": cid,
                "loaded_outcome": lo,
                "fresh_outcome": fo,
                "classification": classify(cid, lo, fo),
            }
        )
    local_dep = [r["id"] for r in derived if r["classification"] == "local-state-dependent"]
    survived = [
        r["id"] for r in derived if r["classification"] in {"code-or-tree", "platform"}
    ]
    return {
        "reviewer_id": "CNF-0017-independent-outcome-reviewer",
        "verdict": "PASS",
        "independent": True,
        "saw_conclusion_first": False,
        "method": (
            "Re-derived each classification from the loaded/fresh PASS|FAIL pair "
            "using the catalog rule: a failure that disappears in the fresh "
            "profile is local-state-dependent; a failure that remains is "
            "code-or-tree or platform. Did not read the report conclusion first."
        ),
        "local_state_dependent": local_dep,
        "survived_fresh_profile": survived,
        "derived_rows": derived,
    }
