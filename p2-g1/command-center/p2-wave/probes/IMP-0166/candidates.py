"""IMP-0166: the candidate stopping-rule set (spec-named + planted controls).

The six spec-named expressions are anchored to the governing spec lines; the
remaining candidates are controls: expressible variants, two deliberately
inexpressible prose rules, and an empty rule.
"""

SPEC_EXPRESSIONS = [
    {"id": "spec-10937", "spec_line": 10937,
     "text": "unique_ideas >= 100 AND completeness_score >= 0.90"},
    {"id": "spec-10938", "spec_line": 10938,
     "text": "consensus >= 0.95 AND no_new_objection_rounds >= 2"},
    {"id": "spec-10939", "spec_line": 10939,
     "text": "unanimity == true OR max_rounds == 12"},
    {"id": "spec-10940", "spec_line": 10940,
     "text": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0"},
    {"id": "spec-10941", "spec_line": 10941,
     "text": "evidence_saturation == true OR time_minutes >= 180"},
    {"id": "spec-10942", "spec_line": 10942,
     "text": "proof_of_impossibility == true"},
]


def candidate_set() -> list:
    rows = [{"id": f"cand-{e['id']}", "source": e["text"]} for e in SPEC_EXPRESSIONS]
    rows += [
        {"id": "cand-expressible-twin-10937",
         "source": "stop when unique_ideas >= 100 AND completeness_score >= 0.90"},
        {"id": "cand-any-all",
         "source": "ALL(unique_ideas >= 100, completeness_score >= 0.90)"},
        {"id": "cand-weighted",
         "source": ("WEIGHTED(0.7, unique_ideas >= 100: 0.4, "
                    "completeness_score >= 0.90: 0.4, consensus >= 0.95: 0.3)")},
        {"id": "cand-inexpressible-feels-done", "source": "stop when it feels done"},
        {"id": "cand-inexpressible-juice",
         "source": "halt when the juice is worth the squeeze"},
        {"id": "cand-none", "source": ""},
    ]
    return rows
