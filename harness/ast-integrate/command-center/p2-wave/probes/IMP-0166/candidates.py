#!/usr/bin/env python3
"""Spec-named stopping expressions (catalog CNL-0078..CNL-0083 titles) plus fixtures."""
from __future__ import annotations

from typing import Any

# Verbatim from WORK-UNIT-CATALOG.json CNL-0078..CNL-0083 titles, which quote
# _USER-PROMPTS.md:10937-10942. The prompts file is not on this worktree.
SPEC_EXPRESSIONS: list[dict[str, Any]] = [
    {
        "id": "spec-10937",
        "spec_line": 10937,
        "text": "unique_ideas >= 100 AND completeness_score >= 0.90",
        "stop_state": {"unique_ideas": 100, "completeness_score": 0.90},
        "continue_state": {"unique_ideas": 99, "completeness_score": 0.90},
        "continue_alt": {"unique_ideas": 100, "completeness_score": 0.89},
        "partial_unknown": {"unique_ideas": 100},
    },
    {
        "id": "spec-10938",
        "spec_line": 10938,
        "text": "consensus >= 0.95 AND no_new_objection_rounds >= 2",
        "stop_state": {"consensus": 0.95, "no_new_objection_rounds": 2},
        "continue_state": {"consensus": 0.94, "no_new_objection_rounds": 2},
        "continue_alt": {"consensus": 0.95, "no_new_objection_rounds": 1},
        "partial_unknown": {"consensus": 0.95},
    },
    {
        "id": "spec-10939",
        "spec_line": 10939,
        "text": "unanimity == true OR max_rounds == 12",
        "stop_state": {"unanimity": True, "max_rounds": 0},
        "stop_alt": {"unanimity": False, "max_rounds": 12},
        "continue_state": {"unanimity": False, "max_rounds": 11},
        "partial_unknown": {"unanimity": False},
    },
    {
        "id": "spec-10940",
        "spec_line": 10940,
        "text": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
        "stop_state": {
            "quality_gate": "PASS",
            "unresolved_load_bearing_counterexample": 0,
        },
        "continue_state": {
            "quality_gate": "PASS",
            "unresolved_load_bearing_counterexample": 1,
        },
        "continue_alt": {
            "quality_gate": "FAIL",
            "unresolved_load_bearing_counterexample": 0,
        },
        "partial_unknown": {"quality_gate": "PASS"},
    },
    {
        "id": "spec-10941",
        "spec_line": 10941,
        "text": "evidence_saturation == true OR time_minutes >= 180",
        "stop_state": {"evidence_saturation": True, "time_minutes": 0},
        "stop_alt": {"evidence_saturation": False, "time_minutes": 180},
        "continue_state": {"evidence_saturation": False, "time_minutes": 179},
        "partial_unknown": {"evidence_saturation": False},
    },
    {
        "id": "spec-10942",
        "spec_line": 10942,
        "text": "proof_of_impossibility == true",
        "stop_state": {"proof_of_impossibility": True, "search_exhausted": True},
        "continue_state": {"proof_of_impossibility": False, "search_exhausted": True},
        "continue_alt": {"proof_of_impossibility": False, "search_exhausted": False},
        "partial_unknown": {},
    },
]

WEIGHTED_EXAMPLE = {
    "id": "weighted-any-all-demo",
    "text": (
        "WEIGHTED(0.7, unique_ideas >= 100: 0.4, "
        "completeness_score >= 0.90: 0.4, consensus >= 0.95: 0.3)"
    ),
    "stop_state": {
        "unique_ideas": 100,
        "completeness_score": 0.90,
        "consensus": 0.0,
    },
    "continue_state": {
        "unique_ideas": 100,
        "completeness_score": 0.0,
        "consensus": 0.0,
    },
    "partial_unknown": {"unique_ideas": 100},
}

INEXPRESSIBLE_ID = "cand-inexpressible-feels-done"
EXPRESSIBLE_TWIN_ID = "cand-expressible-twin-10937"


def candidate_set() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in SPEC_EXPRESSIONS:
        rows.append(
            {
                "id": f"cand-{spec['id']}",
                "stop": spec["text"],
                "origin": f"_USER-PROMPTS.md:{spec['spec_line']}",
            }
        )
    rows.append(
        {
            "id": EXPRESSIBLE_TWIN_ID,
            "stop": "stop when unique_ideas >= 100 AND completeness_score >= 0.90",
            "origin": "wrapper-normalisation-control",
        }
    )
    rows.append(
        {
            "id": "cand-any-all",
            "stop": "ALL(unique_ideas >= 100, completeness_score >= 0.90)",
            "origin": "_USER-PROMPTS.md:10760 ANY/ALL form of 10937",
        }
    )
    rows.append(
        {
            "id": "cand-weighted",
            "stop": WEIGHTED_EXAMPLE["text"],
            "origin": "_USER-PROMPTS.md:10760 weighted logic",
        }
    )
    rows.append(
        {
            "id": INEXPRESSIBLE_ID,
            "stop": "stop when it feels done",
            "origin": "planted-inexpressible",
        }
    )
    rows.append(
        {
            "id": "cand-inexpressible-juice",
            "stop": "halt when the juice is worth the squeeze",
            "origin": "planted-inexpressible",
        }
    )
    rows.append(
        {
            "id": "cand-none",
            "stop": "",
            "origin": "missing-stop-rule",
        }
    )
    return rows
