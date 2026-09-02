#!/usr/bin/env python3
"""Probe 1: estimate-vs-actual error is a COMPUTED number, same units.

Live: re-run the hermetic registry, compute median absolute error, refuse
the adjective 'accurate'. If the receipt already exists, its recorded error
must match this live number (green-not-live control).
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.registry import evaluate_registry  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0143.json"
ESTIMATOR = REPO / "tools/agentspec/agentspec/estimator.py"
BUDGET = REPO / "tools/agentspec/agentspec/budget.py"
ADJECTIVES = {"accurate", "good", "close", "calibrated", "fine", "ok"}


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0143-probe1 {msg}")
    return 1


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def ast_estimator_reuses_budget() -> str | None:
    src = ESTIMATOR.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("budget"):
            imported.update(a.name for a in node.names)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "KIND_RATES":
                    return "estimator assigns KIND_RATES (second rate table)"
    if "BudgetLedger" not in imported:
        return f"estimator does not import BudgetLedger from budget: {sorted(imported)}"
    if "charge" not in imported:
        return f"estimator does not import charge from budget: {sorted(imported)}"
    budget_src = BUDGET.read_text(encoding="utf-8")
    if "KIND_RATES" not in budget_src:
        return "budget.py missing KIND_RATES"
    if "time.time" in src or "datetime" in src:
        return "estimator reads a clock"
    return None


def main() -> int:
    why = ast_estimator_reuses_budget()
    print(f"ast_reuses_budget={why is None} {why or 'ok'}")
    if why:
        return _fail(why)

    with tempfile.TemporaryDirectory(prefix="imp0143-p1-") as tmp:
        report = evaluate_registry(Path(tmp))

    mae = report["median_absolute_error"]
    err = report["estimator_error"]
    print(json.dumps(
        {
            "n_cases": report["n_cases"],
            "median_absolute_error": mae,
            "estimator_error": err,
            "all_same_units": report["all_same_units"],
            "units": report["units"],
            "rows": [
                {
                    "case_id": r["case_id"],
                    "abs_err_micro_cost": r["abs_err_micro_cost"],
                    "abs_err_wall_clock_ms": r["abs_err_wall_clock_ms"],
                    "same_units": r["same_units"],
                }
                for r in report["rows"]
            ],
        },
        indent=2,
        sort_keys=True,
    ))

    if report["n_cases"] < 5:
        return _fail(f"registry too small n={report['n_cases']}")
    if not report["all_same_units"]:
        return _fail("estimate and actual not in the same units")
    if not _is_number(err):
        return _fail(f"estimator_error is not a number: {err!r}")
    if isinstance(err, str) or str(err).strip().lower() in ADJECTIVES:
        return _fail("estimator_error is an adjective, not a number")
    if not _is_number(mae["micro_cost"]) or not _is_number(mae["wall_clock_ms"]):
        return _fail(f"MAE breakdown is not numeric: {mae!r}")
    if err != mae["micro_cost"]:
        return _fail("estimator_error != median_absolute_error.micro_cost")

    # Both-states: stuffing the adjective must be rejected by the same checker.
    if _is_number("accurate"):
        return _fail("number checker accepted the adjective 'accurate'")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"self-declared {doc.get('state')}")
        recorded = doc.get("estimator_error")
        if not _is_number(recorded):
            return _fail(f"receipt estimator_error not a number: {recorded!r}")
        if recorded != err:
            return _fail(
                f"receipt estimator_error={recorded} != live {err} (green-not-live)"
            )
        rec_mae = doc.get("median_absolute_error") or {}
        if rec_mae.get("micro_cost") != mae["micro_cost"]:
            return _fail("receipt MAE micro_cost drifted from live")
        if rec_mae.get("wall_clock_ms") != mae["wall_clock_ms"]:
            return _fail("receipt MAE wall_clock_ms drifted from live")
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0143" not in text:
            return _fail("sentinel absent from receipt")

    print("SUCCESS:IMP-0143-probe1 estimate-vs-actual MAE is a computed number")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
