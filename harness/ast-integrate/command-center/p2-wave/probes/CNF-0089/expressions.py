#!/usr/bin/env python3
"""The six required stopping expressions (spec lines 10937-10942).

Quoted from catalog CNL-0078..CNL-0083 titles and TST-0281/CNF-0089 inputs.
_USER-PROMPTS.md is not in this worktree; these strings are the catalog's
verbatim examples for those line numbers.
"""
from __future__ import annotations

EXPRESSIONS: list[dict] = [
    {
        "id": "E1",
        "spec_line": 10937,
        "text": "unique_ideas >= 100 AND completeness_score >= 0.90",
        "connective": "AND",
        "title": "unique_ideas >= 100 AND completeness_score >= 0.90",
    },
    {
        "id": "E2",
        "spec_line": 10938,
        "text": "consensus >= 0.95 AND no_new_objection_rounds >= 2",
        "connective": "AND",
        "title": "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    },
    {
        "id": "E3",
        "spec_line": 10939,
        "text": "unanimity == true OR max_rounds == 12",
        "connective": "OR",
        "title": "unanimity == true OR max_rounds == 12",
    },
    {
        "id": "E4",
        "spec_line": 10940,
        "text": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
        "connective": "AND",
        "title": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    },
    {
        "id": "E5",
        "spec_line": 10941,
        "text": "evidence_saturation == true OR time_minutes >= 180",
        "connective": "OR",
        "title": "evidence_saturation == true OR time_minutes >= 180",
    },
    {
        "id": "E6",
        "spec_line": 10942,
        "text": "proof_of_impossibility == true",
        "connective": "ATOM",
        "title": "proof_of_impossibility == true",
    },
]

NEVER_TRUE = "unique_ideas >= 100 AND unique_ideas < 100"
