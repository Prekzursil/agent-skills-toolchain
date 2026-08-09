"""Probe: do TWO independent stopping-expression implementations agree?

`platform/lib/wfdsl/expr.py` (sibling unit, written independently) and
`platform/lib/councilspec/expression.py` (this unit) both parse and evaluate the six required
spec expressions. Agreement between them is a second, mechanically independent signal; a
disagreement is a defect in one of them and must be reported, not averaged.

Read-only. Writes nothing but stdout.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from councilspec import expression as mine  # noqa: E402

CASES = [
    (
        "unique_ideas >= 100 AND completeness_score >= 0.90",
        {"unique_ideas": 104, "completeness_score": 0.93},
        {"unique_ideas": 104, "completeness_score": 0.80},
    ),
    (
        "consensus >= 0.95 AND no_new_objection_rounds >= 2",
        {"consensus": 0.96, "no_new_objection_rounds": 2},
        {"consensus": 0.96, "no_new_objection_rounds": 1},
    ),
    (
        "unanimity == true OR max_rounds == 12",
        {"unanimity": False, "max_rounds": 12},
        {"unanimity": False, "max_rounds": 11},
    ),
    (
        "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
        {"quality_gate": "PASS", "unresolved_load_bearing_counterexample": 0},
        {"quality_gate": "PASS", "unresolved_load_bearing_counterexample": 1},
    ),
    (
        "evidence_saturation == true OR time_minutes >= 180",
        {"evidence_saturation": False, "time_minutes": 181},
        {"evidence_saturation": False, "time_minutes": 179},
    ),
    (
        "proof_of_impossibility == true",
        {"proof_of_impossibility": True},
        {"proof_of_impossibility": False},
    ),
]


def main() -> int:
    try:
        from wfdsl import expr as theirs
    except Exception as exc:  # noqa: BLE001
        print(
            f"NOT-CHECKED: sibling wfdsl.expr unavailable ({type(exc).__name__}: {exc})"
        )
        return 3

    agree = disagree = errored = 0
    for text, sat, unsat in CASES:
        row = [text[:58].ljust(58)]
        try:
            m_true = mine.evaluate(mine.parse(text), sat)
            m_false = mine.evaluate(mine.parse(text), unsat)
        except Exception as exc:  # noqa: BLE001
            print(f"{row[0]} MINE-ERROR {type(exc).__name__}: {exc}")
            errored += 1
            continue
        try:
            t_true = theirs.evaluate(text, sat)
            t_false = theirs.evaluate(text, unsat)
        except Exception as exc:  # noqa: BLE001
            print(f"{row[0]} THEIRS-ERROR {type(exc).__name__}: {str(exc)[:90]}")
            errored += 1
            continue
        same = (m_true, m_false) == (t_true, t_false)
        both_states_ok = (m_true, m_false) == (True, False)
        verdict = "AGREE" if same else "DISAGREE"
        if same:
            agree += 1
        else:
            disagree += 1
        print(
            f"{row[0]} mine=({m_true},{m_false}) theirs=({t_true},{t_false}) "
            f"{verdict} both_states={'OK' if both_states_ok else 'BROKEN'}"
        )

    print(f"\nagree={agree} disagree={disagree} errored={errored} of {len(CASES)}")
    print(
        "SUCCESS:cross-impl-agreement"
        if disagree == 0 and errored == 0
        else "FAILED:cross-impl-agreement independent implementations differ"
    )
    return 0 if (disagree == 0 and errored == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
