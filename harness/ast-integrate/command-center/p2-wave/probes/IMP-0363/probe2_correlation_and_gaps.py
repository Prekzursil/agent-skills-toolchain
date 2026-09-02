#!/usr/bin/env python3
"""Probe 2: popularity-versus-examination correlation and coverage-gap control.

Mechanically different from probe 1 (set-completeness / depth). This probe
publishes Pearson r with its sign, and asserts a deliberately unexamined
position is reported as a gap (both-states against the intact schedule).
"""
from __future__ import annotations

import ast
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.crossexam import (  # noqa: E402
    coverage_gaps,
    coverage_matrix,
    drop_position_pairings,
    popularity_examination_correlation,
    schedule_cross_examination,
    weak_only_schedule,
)
from fixtures import MAX_DEPTH, PARTICIPANTS, labelled_positions  # noqa: E402

MODULE = REPO / "tools/council/protocol/crossexam.py"


def independent_pearson(xs: list[float], ys: list[float]) -> dict:
    n = len(xs)
    if n < 2 or n != len(ys):
        return {"coefficient": None, "sign": "undefined", "n": n, "reason": "n"}
    mx = sum(xs) / n
    my = sum(ys) / n
    num = varx = vary = 0.0
    for x, y in zip(xs, ys):
        num += (x - mx) * (y - my)
        varx += (x - mx) ** 2
        vary += (y - my) ** 2
    if varx == 0.0 or vary == 0.0:
        return {
            "coefficient": None,
            "sign": "undefined",
            "n": n,
            "reason": "zero-variance",
        }
    r = num / math.sqrt(varx * vary)
    sign = "positive" if r > 0 else "negative" if r < 0 else "zero"
    return {"coefficient": r, "sign": sign, "n": n, "reason": None}


def _gaps_not_stub() -> bool:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "coverage_gaps":
            body = [n for n in node.body if not isinstance(n, (ast.Expr, ast.Pass))]
            if len(body) == 1 and isinstance(body[0], ast.Return):
                val = body[0].value
                if isinstance(val, (ast.List, ast.Tuple)) and not val.elts:
                    return False
                if isinstance(val, ast.Constant) and val.value in ((), []):
                    return False
            return True
    return False


def main() -> int:
    positions = labelled_positions()
    good = schedule_cross_examination(positions, PARTICIPANTS, max_depth=MAX_DEPTH)
    xs = [r.popularity for r in good.coverage if r.substantive]
    ys = [float(r.examination_count) for r in good.coverage if r.substantive]
    indep = independent_pearson(xs, ys)
    module_corr = popularity_examination_correlation(good.coverage)
    corr_match = (
        indep["sign"] == module_corr.sign == good.correlation.sign == "positive"
        and indep["coefficient"] is not None
        and module_corr.coefficient is not None
        and abs(indep["coefficient"] - module_corr.coefficient) < 1e-12
    )

    planted = drop_position_pairings(positions, good, "P-dom")
    planted_gaps = coverage_gaps(planted.coverage)
    gap_fires = (
        planted.complete is False
        and "P-dom" in planted_gaps
        and any(r.position_id == "P-dom" and r.gap for r in planted.coverage)
    )
    good_silent = good.complete is True and list(good.gaps) == []

    proc_drop = drop_position_pairings(positions, good, "P-proc")
    proc_not_gap = "P-proc" not in proc_drop.gaps and proc_drop.complete is True

    mutant = weak_only_schedule(positions, PARTICIPANTS, max_depth=MAX_DEPTH)
    mutant_corr = mutant.correlation
    mutant_fires = (
        mutant.complete is False
        and "P-dom" in mutant.gaps
        and mutant.bias.favours_weak_leaves_dominant_unchallenged is True
        and mutant_corr.sign == "negative"
        and good.bias.favours_weak_leaves_dominant_unchallenged is False
    )

    matrix = coverage_matrix(positions, good.pairings)
    matrix_ids = [r.position_id for r in matrix]
    expected_ids = [p.position_id for p in positions]
    matrix_ok = matrix_ids == expected_ids and all(
        r.examination_count == next(
            c.examination_count
            for c in good.coverage
            if c.position_id == r.position_id
        )
        for r in matrix
    )

    payload = {
        "probe": "probe2-correlation-and-gaps",
        "unit_id": "IMP-0363",
        "coverage_matrix": [r.__dict__ for r in good.coverage],
        "correlation": good.correlation.as_dict(),
        "independent_correlation": indep,
        "corr_match": corr_match,
        "sign_published": good.correlation.sign,
        "both_states_gap": {
            "good_silent": good_silent,
            "planted_unexamined_dominant_fires": gap_fires,
            "planted_gaps": list(planted_gaps),
        },
        "non_substantive_drop_not_a_gap": proc_not_gap,
        "weak_only_mutant": {
            "complete": mutant.complete,
            "gaps": list(mutant.gaps),
            "sign": mutant_corr.sign,
            "coefficient": mutant_corr.coefficient,
            "favours_weak_leaves_dominant": (
                mutant.bias.favours_weak_leaves_dominant_unchallenged
            ),
            "fires": mutant_fires,
        },
        "production_bias": good.bias.as_dict(),
        "matrix_ok": matrix_ok,
        "coverage_gaps_not_stub": _gaps_not_stub(),
    }
    payload["pass"] = bool(
        corr_match
        and good_silent
        and gap_fires
        and proc_not_gap
        and mutant_fires
        and matrix_ok
        and payload["coverage_gaps_not_stub"]
        and indep["sign"] == "positive"
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=list))
    if not payload["pass"]:
        print("FAILED:IMP-0363-probe2 correlation or coverage gap")
        return 1
    print(
        "SUCCESS:IMP-0363-probe2 popularity-examination correlation "
        f"sign={good.correlation.sign} planted-gap-fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
