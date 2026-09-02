#!/usr/bin/env python3
"""Build the 6x2 stopping-rule table from fixtures (parser + direct recount)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import direct as D  # noqa: E402
import expr as E  # noqa: E402
import fixtures as F  # noqa: E402


def _cell(
    expression_id: str,
    expression: str,
    state: str,
    fixture_name: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    public = {k: v for k, v in metrics.items() if not str(k).startswith("_")}
    parsed = E.evaluate(expression, public)
    recounted = D.evaluate_id(expression_id, public)
    if parsed != recounted:
        raise SystemExit(
            f"BLOCKED:CNL-0121 parser/direct disagree {expression_id} {state}: "
            f"parser={parsed!r} direct={recounted!r}"
        )
    expected = "FIRE" if state == "true" else "SILENT"
    observed = E.observed(parsed)
    verdict = "PASS" if observed == expected else "FAIL"
    verbatim = (
        f"{expression_id} {state}: expected={expected} observed={observed} "
        f"eval={parsed!r} fixture={fixture_name} metrics={json.dumps(public, sort_keys=True)}"
    )
    return {
        "expression_id": expression_id,
        "state": state,
        "expected": expected,
        "observed": observed,
        "verdict": verdict,
        "verbatim": verbatim,
        "fixture": fixture_name,
        "eval": {True: True, False: False, None: "NOT-CHECKED"}[parsed]
        if parsed in (True, False) or parsed is None
        else parsed,
        "metrics": public,
    }


def run_table() -> dict[str, Any]:
    rows = []
    cells = []
    for spec in F.expressions():
        eid = spec["id"]
        expression = spec["expression"]
        true_name = spec["true_fixture"]
        false_name = spec["false_fixture"]
        _, true_m = F.load_fixture(true_name)
        _, false_m = F.load_fixture(false_name)
        true_cell = _cell(eid, expression, "true", true_name, true_m)
        false_cell = _cell(eid, expression, "false", false_name, false_m)
        rows.append(
            {
                "expression_id": eid,
                "source_unit": spec["source_unit"],
                "expression": expression,
                "true_state": {
                    "expected": true_cell["expected"],
                    "observed": true_cell["observed"],
                    "verdict": true_cell["verdict"],
                    "verbatim": true_cell["verbatim"],
                    "fixture": true_cell["fixture"],
                },
                "false_state": {
                    "expected": false_cell["expected"],
                    "observed": false_cell["observed"],
                    "verdict": false_cell["verdict"],
                    "verbatim": false_cell["verbatim"],
                    "fixture": false_cell["fixture"],
                },
            }
        )
        cells.extend([true_cell, false_cell])
    populated = [c for c in cells if c["observed"] in {"FIRE", "SILENT", "NOT-CHECKED"}]
    failed = [c for c in cells if c["verdict"] != "PASS"]
    not_checked = [c for c in cells if c["observed"] == "NOT-CHECKED"]
    return {
        "rows": rows,
        "cells": cells,
        "cell_count": len(cells),
        "populated_cells": len(populated),
        "unpopulated_cells": 12 - len(populated),
        "failed": failed,
        "not_checked": not_checked,
        "fire_on_true": sum(1 for c in cells if c["state"] == "true" and c["observed"] == "FIRE"),
        "silent_on_false": sum(
            1 for c in cells if c["state"] == "false" and c["observed"] == "SILENT"
        ),
    }


def mutant_and_as_or(expression: str, metrics: dict[str, Any]) -> bool | None:
    """Broken evaluator: any true AND-conjunct fires. Used as a negative control."""
    if " AND " not in expression:
        return E.evaluate(expression, metrics)
    parts = [p.strip() for p in expression.split(" AND ")]
    values = [E.evaluate(p, metrics) for p in parts]
    if any(v is True for v in values):
        return True
    if any(v is None for v in values):
        return None
    return False


def negative_controls() -> list[dict[str, Any]]:
    catalog = {s["id"]: s for s in F.expressions()}
    out = []

    one = F.load_json(F.FIX / "negative" / "and-one-false.json")
    expr = catalog[one["expression_id"]]["expression"]
    real = E.evaluate(expr, one["metrics"])
    mutant = mutant_and_as_or(expr, one["metrics"])
    obs = E.observed(real)
    verbatim = (
        f"NEG and-one-false: real={obs} eval={real!r} mutant_and_as_or="
        f"{E.observed(mutant)} mutant_eval={mutant!r} metrics="
        f"{json.dumps(one['metrics'], sort_keys=True)}"
    )
    out.append(
        {
            "id": "and-one-false",
            "rejects": one["note"],
            "observed": obs,
            "verbatim": verbatim,
            "pass": obs == "SILENT" and mutant is True,
        }
    )

    missing = F.load_json(F.FIX / "negative" / "and-missing-conjunct.json")
    real_m = E.evaluate(expr, missing["metrics"])
    mutant_m = mutant_and_as_or(expr, missing["metrics"])
    obs_m = E.observed(real_m)
    verbatim_m = (
        f"NEG and-missing-conjunct: real={obs_m} eval={real_m!r} mutant_and_as_or="
        f"{E.observed(mutant_m)} mutant_eval={mutant_m!r} metrics="
        f"{json.dumps(missing['metrics'], sort_keys=True)}"
    )
    out.append(
        {
            "id": "and-missing-conjunct",
            "rejects": missing["note"],
            "observed": obs_m,
            "verbatim": verbatim_m,
            "pass": obs_m == "NOT-CHECKED" and mutant_m is True,
        }
    )

    search = F.load_json(F.FIX / "negative" / "unsuccessful-search.json")
    e6 = catalog["E6"]["expression"]
    metrics_e6 = {"proof_of_impossibility": False}
    real_e6 = E.evaluate(e6, metrics_e6)
    planted = E.evaluate(e6, {"proof_of_impossibility": True})
    obs_e6 = E.observed(real_e6)
    verbatim_e6 = (
        f"NEG unsuccessful-search: real={obs_e6} eval={real_e6!r} "
        f"search_log_attempts={search.get('attempts')} hits={search.get('hits')} "
        f"planted_true_would={E.observed(planted)} "
        f"note={search.get('note')}"
    )
    out.append(
        {
            "id": "unsuccessful-search",
            "rejects": search["note"],
            "observed": obs_e6,
            "verbatim": verbatim_e6,
            "pass": obs_e6 == "SILENT" and planted is True,
        }
    )

    always_true_false_cells = 0
    real_silent_false = 0
    table = run_table()
    for cell in table["cells"]:
        if cell["state"] != "false":
            continue
        real_silent_false += int(cell["observed"] == "SILENT")
        always_true_false_cells += 1
    out.append(
        {
            "id": "vacuous-always-fire",
            "rejects": "A detector that fires on every fixture (true and false) measures nothing.",
            "observed": "SILENT",
            "verbatim": (
                f"NEG vacuous-always-fire: mutant would FIRE on all "
                f"{always_true_false_cells} false fixtures; real evaluator SILENT on "
                f"{real_silent_false}/{always_true_false_cells} false fixtures"
            ),
            "pass": real_silent_false == always_true_false_cells == 6,
        }
    )
    return out
