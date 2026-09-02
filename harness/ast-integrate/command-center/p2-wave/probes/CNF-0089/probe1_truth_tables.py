#!/usr/bin/env python3
"""Probe 1: live full truth tables for all six stopping expressions.

Every 3-valued row is driven. Sampling is a failure. STOP must match Kleene
True. AND must not behave as OR on the honest runtime. proof_of_impossibility
must be reachable. The never-true control must never STOP.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import tables as T  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0089-stopping-truth-table.json"
SENTINEL = (
    "SUCCESS:CNF-0089 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every row of every one "
    "of the six truth tables has an observed outcome, with no sampled rows. "
    "Any other terminal state is FAILED:CNF-0089 <classification> with the "
    "diagnostic tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0089-probe1 {msg}")
    return 1


def main() -> int:
    live = T.drive_all()
    print(
        json.dumps(
            {
                "total_rows_observed": live["total_rows_observed"],
                "total_rows_expected": live["total_rows_expected"],
                "sampled": live["sampled"],
                "all_six_complete": live["all_six_complete"],
                "runtime_conforms": live["runtime_conforms"],
                "and_as_or_on_honest": live["and_as_or_on_honest"],
                "poi_reachable": live["proof_of_impossibility"]["reachable"],
                "never_stopped": live["never_true_control"]["never_stopped"],
                "per_table": [
                    {
                        "id": t["id"],
                        "rows": t["observed_row_count"],
                        "expected": t["expected_row_count"],
                        "conforms": t["conforms"],
                        "sampled": t["sampled"],
                    }
                    for t in live["tables"]
                ],
            },
            sort_keys=True,
        )
    )
    if live["sampled"] or not live["all_six_complete"]:
        return fail("partial-table or sampled rows")
    if live["total_rows_observed"] != live["total_rows_expected"]:
        return fail("row census mismatch")
    if not live["runtime_conforms"]:
        return fail("boolean-semantics-defect runtime != spec")
    if live["and_as_or_on_honest"]:
        return fail("AND behaved as OR under partial evidence")
    if not live["proof_of_impossibility"]["reachable"]:
        return fail("proof_of_impossibility unreachable")
    if not live["never_true_control"]["never_stopped"]:
        return fail("never-true control stopped")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    census = doc.get("row_census") or {}
    if int(census.get("observed") or 0) != live["total_rows_observed"]:
        return fail("artifact row census != live drive")
    if census.get("sampled") is not False:
        return fail("artifact sampled flag")
    tables = doc.get("truth_tables") or []
    if len(tables) != 6:
        return fail(f"artifact table count {len(tables)}")
    for t in tables:
        if t.get("sampled") is not False:
            return fail(f"{t.get('id')} sampled")
        if int(t.get("observed_row_count") or 0) != int(t.get("expected_row_count") or -1):
            return fail(f"{t.get('id')} incomplete")
        if len(t.get("rows") or []) != int(t.get("expected_row_count") or -1):
            return fail(f"{t.get('id')} rows array short")
    print(
        f"rows={live['total_rows_observed']}/{live['total_rows_expected']} "
        f"conforms={live['runtime_conforms']} and_as_or={live['and_as_or_on_honest']}"
    )
    print("SUCCESS:CNF-0089-probe1 full truth tables observed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
