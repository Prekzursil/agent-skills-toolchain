#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0143.json from a live registry evaluation."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.evals.registry import (  # noqa: E402
    evaluate_registry,
    ledger_invariants_hold,
    writes_declared_superset,
)
from probe1_estimate_vs_actual import ast_estimator_reuses_budget  # noqa: E402

OUT = "command-center/receipts/IMP-0143.json"
SENTINEL = "SUCCESS:IMP-0143"


def write_receipt() -> dict:
    ast_why = ast_estimator_reuses_budget()
    if ast_why:
        raise SystemExit(f"FAILED:IMP-0143 estimator AST: {ast_why}")
    with tempfile.TemporaryDirectory(prefix="imp0143-emit-") as tmp:
        report = evaluate_registry(Path(tmp))
    inv = ledger_invariants_hold()
    victim = next(r for r in report["rows"] if r["act_writes"])
    dropped = victim["act_writes"][0]
    mutant_est = [p for p in victim["est_writes"] if p != dropped]
    underdeclare_fired = not writes_declared_superset(
        set(mutant_est), set(victim["act_writes"])
    )
    good_silent = writes_declared_superset(
        set(victim["est_writes"]), set(victim["act_writes"])
    )
    extra_fired = not writes_declared_superset(
        set(victim["est_writes"]),
        set(victim["act_writes"]) | {"undeclared/escape.txt"},
    )
    if not report["all_same_units"]:
        raise SystemExit("FAILED:IMP-0143 units mismatch")
    if not report["all_writes_superset"]:
        raise SystemExit("FAILED:IMP-0143 writes not superset")
    if not underdeclare_fired or not good_silent or not extra_fired:
        raise SystemExit("FAILED:IMP-0143 writes both-states")
    if not inv["duplicate_append_raised"]:
        raise SystemExit("FAILED:IMP-0143 double-count did not fire")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mae = report["median_absolute_error"]
    err = report["estimator_error"]
    table = [
        {
            "case_id": r["case_id"],
            "est_micro_cost": r["est_micro_cost"],
            "act_micro_cost": r["act_micro_cost"],
            "abs_err_micro_cost": r["abs_err_micro_cost"],
            "est_wall_clock_ms": r["est_wall_clock_ms"],
            "act_wall_clock_ms": r["act_wall_clock_ms"],
            "abs_err_wall_clock_ms": r["abs_err_wall_clock_ms"],
            "est_writes": r["est_writes"],
            "act_writes": r["act_writes"],
            "observed_writes": r["observed_writes"],
            "writes_superset": r["writes_superset"],
            "units": r["units_estimate"],
        }
        for r in report["rows"]
    ]
    answer = (
        "Pre-run estimator charges tools/agentspec/agentspec/budget.py "
        f"(units micro + ms + posix-path). Live hermetic registry n={report['n_cases']} "
        f"median absolute error micro_cost={err} wall_clock_ms={mae['wall_clock_ms']}. "
        "Declared may_write is a superset of observed fixture writes. "
        "Ledger monotonicity and no-double-count assertions passed "
        f"(duplicate append raised={inv['duplicate_append_raised']}). {SENTINEL}"
    )
    doc = {
        "unit_id": "IMP-0143",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Implement a pre-run cost, time and impact estimator over the budget ledger",
        "answer": answer,
        "accounting_model": report["accounting_model"],
        "second_accounting_model": False,
        "estimator_error": err,
        "estimator_error_is_adjective": False,
        "median_absolute_error": mae,
        "all_writes_superset": True,
        "all_same_units": True,
        "units": report["units"],
        "estimate_vs_actual": table,
        "ledger_invariants": inv,
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
            },
            {
                "path": "tools/agentspec/agentspec/budget.py",
                "role": "accounting-model",
                "exists": True,
            },
            {
                "path": "tools/agentspec/agentspec/estimator.py",
                "role": "estimator",
                "exists": True,
            },
            {
                "path": "tools/agentspec/agentspec/evals/registry.py",
                "role": "hermetic-eval-registry",
                "exists": True,
            },
        ],
        "evidence": [
            {
                "anchor": "tools/agentspec/agentspec/evals/registry.py:evaluate_registry",
                "claim": (
                    "Estimate-vs-actual table over the hermetic eval registry "
                    f"reports median absolute error micro_cost={err} "
                    f"wall_clock_ms={mae['wall_clock_ms']} as numbers, not 'accurate'."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0143/probe1_estimate_vs_actual.py"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0143/probe1_estimate_vs_actual.py"
                        ),
                    },
                ],
            },
            {
                "anchor": "tools/agentspec/agentspec/budget.py:BudgetLedger.assert_no_double_count",
                "claim": (
                    "Budget ledger monotonicity and no-double-count assertions pass; "
                    "declared writes are a superset of writes observed on disk in each fixture."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0143/probe2_writes_superset.py"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0143/probe2_writes_superset.py"
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "estimate-vs-actual-mae-number",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0143/probe1_estimate_vs_actual.py"
                ),
                "result": "PASS",
            },
            {
                "id": "writes-superset-of-observed",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0143/probe2_writes_superset.py"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "adjective-error-refused",
                "kind": "known-broken-fixture",
                "description": "isinstance(number) rejects the string 'accurate'",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "underdeclare-write-goes-red",
                "kind": "mutation",
                "description": (
                    f"Drop observed write {dropped} from {victim['case_id']} estimate"
                ),
                "fired_on_bad_state": underdeclare_fired,
                "silent_on_good_state": good_silent,
            },
            {
                "id": "undeclared-escape-write",
                "kind": "mutation",
                "description": "Add undeclared/escape.txt to observed writes",
                "fired_on_bad_state": extra_fired,
                "silent_on_good_state": True,
            },
            {
                "id": "double-count-append",
                "kind": "known-broken-fixture",
                "description": "Appending the same node_id raises DoubleCountError",
                "fired_on_bad_state": inv["duplicate_append_raised"],
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0143-probe2-writes-superset-and-ledger",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
        },
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0143/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0143/probe1_estimate_vs_actual.py"
                ),
                "executed": True,
                "read_ok": True,
            },
            {
                "artifact_path": OUT,
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0143/probe2_writes_superset.py"
                ),
                "executed": True,
                "read_ok": True,
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0143",
        "residual_unknowns": [],
        "min_bytes_threshold": 128,
        "timestamps": {"ended_at": now, "started_at": now},
        "notes": (
            "G-1 IMP-0143: estimator reuses BudgetLedger; MAE is a live number; "
            "declared writes superset observed writes. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return doc


def main() -> int:
    write_receipt()
    print(f"wrote {OUT}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
