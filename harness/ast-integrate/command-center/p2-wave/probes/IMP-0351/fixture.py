"""Shared overturn fixture for IMP-0351 probes."""

from __future__ import annotations

from typing import Any

from tools.council.outcomes.lineage_export import empty_log, sample_binding

QUESTION = (
    "When a later council overturns an earlier decision, must the older "
    "program-log entry carry a supersession marker?"
)

OLDER = sample_binding(
    "DEC-0351-A",
    "council-0351-alpha",
    QUESTION,
    "yes — mark the older entry SUPERSEDED",
    tally={"for": 4, "against": 1, "abstain": 0},
    dissents=[
        {
            "actor": "seat-skeptic",
            "claim": "Silent coexistence of two live rows is cheaper to implement.",
        }
    ],
    inputs=[
        {"kind": "charter", "ref": "charter:council-0351-alpha"},
        {"kind": "catalog", "ref": "command-center/WORK-UNIT-CATALOG.json#IMP-0351"},
    ],
)

NEWER = sample_binding(
    "DEC-0351-B",
    "council-0351-bravo",
    QUESTION,
    "no — two contradictory LIVE rows may coexist",
    tally={"for": 3, "against": 2, "abstain": 0},
    dissents=[
        {
            "actor": "seat-archivist",
            "claim": "Two live answers to the same question make recall lie.",
        }
    ],
    inputs=[
        {"kind": "charter", "ref": "charter:council-0351-bravo"},
        {"kind": "prior-decision", "ref": "DEC-0351-A"},
    ],
    rule_id="majority-of-seated-voters",
)


def seeded_log() -> dict[str, Any]:
    from tools.council.outcomes.lineage_export import append_binding

    doc = empty_log()
    append_binding(doc, OLDER)
    return doc
