#!/usr/bin/env python3
"""Probe 1: every condition returns a tri-state; aggregation does not fold NOT-CHECKED."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluator as Ev  # noqa: E402
import live_state as LS  # noqa: E402
import predicate_table as PT  # noqa: E402

REPO = HERE.parents[3]
RECEIPT = REPO / "command-center" / "receipts" / "CC-0015.json"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0015-probe1 {msg}")
    return 1


def synthetic_rows(n_true: int, n_false: int, n_nc: int) -> list[dict]:
    rows = []
    cid = 1
    for _ in range(n_true):
        rows.append({"id": cid, "verdict": "TRUE", "settling_probe": "n/a"})
        cid += 1
    for _ in range(n_false):
        rows.append({"id": cid, "verdict": "FALSE", "settling_probe": "n/a"})
        cid += 1
    for _ in range(n_nc):
        rows.append({"id": cid, "verdict": "NOT-CHECKED", "settling_probe": "probe-missing"})
        cid += 1
    return rows


def main() -> int:
    table = PT.encodings()
    if len(table) != 21:
        return fail(f"encoding-count={len(table)}")
    if [e["id"] for e in table] != list(range(1, 22)):
        return fail("encoding-ids")
    if [e["spec_line"] for e in table] != list(range(11378, 11399)):
        return fail("spec-lines")

    live = LS.load_live_state()
    out = Ev.run(live, table)
    rows = out["conditions"]
    agg = out["aggregation"]
    if out.get("inherited_from_phase_graph") is not False:
        return fail("inherited-phase-graph")
    if live.get("phase_graph_inherited") is not False:
        return fail("live-state-inherited-phase-graph")
    if live["input_presence"].get("PHASE_GRAPH_program_preconditions"):
        # Field is currently absent; if it appears, still must not be used as evidence.
        pass
    if len(rows) != 21:
        return fail(f"live-row-count={len(rows)}")

    for row in rows:
        if row.get("verdict") not in Ev.VERDICTS:
            return fail(f"empty-verdict id={row.get('id')} {row.get('verdict')!r}")
        if not row.get("evidence_pointer"):
            return fail(f"missing-evidence id={row.get('id')}")
        if not row.get("settling_probe"):
            return fail(f"missing-settling-probe id={row.get('id')}")
        cost = row.get("probe_cost") or {}
        if not isinstance(cost.get("approx_seconds"), int):
            return fail(f"missing-probe-cost id={row.get('id')}")

    counts = agg["counts"]
    if set(counts) != Ev.VERDICTS:
        return fail(f"count-keys={sorted(counts)}")
    if counts["TRUE"] + counts["FALSE"] + counts["NOT-CHECKED"] != 21:
        return fail("counts-do-not-sum-to-21")
    if agg.get("not_checked_folded_into_pass") is not False:
        return fail("not-checked-folded")
    if counts["NOT-CHECKED"] > 0 and agg["program_complete"] is True:
        return fail("not-checked-folded-into-program-complete")
    if agg["program_complete"] is True:
        return fail("live-tree-program-complete-would-be-green-not-live")
    if agg["program_verdict"] != "PROGRAM-INCOMPLETE":
        return fail(f"live-verdict={agg['program_verdict']}")

    a20 = Ev.aggregate(synthetic_rows(20, 0, 1))
    if a20["program_complete"] is True or a20["program_verdict"] != "PROGRAM-INCOMPLETE":
        return fail("agg-20-true-1-nc-complete")
    if a20["counts"]["NOT-CHECKED"] != 1 or a20["counts"]["TRUE"] != 20:
        return fail("agg-20-true-1-nc-counts")
    if a20["true_plus_not_checked"] == 21 and a20["program_complete"] is True:
        return fail("agg-folded-nc-into-true")

    a21 = Ev.aggregate(synthetic_rows(21, 0, 0))
    if a21["program_complete"] is not True or a21["program_verdict"] != "PROGRAM-COMPLETE":
        return fail("agg-21-true-not-complete")

    a_false = Ev.aggregate(synthetic_rows(20, 1, 0))
    if a_false["program_complete"] is True:
        return fail("agg-20-true-1-false-complete")

    try:
        Ev.aggregate(
            [{"id": i, "verdict": "TRUE"} for i in range(1, 21)]
            + [{"id": 21, "verdict": ""}]
        )
        return fail("empty-verdict-not-rejected")
    except ValueError:
        pass

    print(
        "conditions=21 "
        f"TRUE={counts['TRUE']} FALSE={counts['FALSE']} "
        f"NOT-CHECKED={counts['NOT-CHECKED']} "
        f"program_complete={agg['program_complete']} "
        f"inherited_phase_graph={out['inherited_from_phase_graph']}"
    )
    print(
        "agg_control 20TRUE+1NC "
        f"complete={a20['program_complete']} "
        "21TRUE "
        f"complete={a21['program_complete']}"
    )
    print("SUCCESS:CC-0015-probe1 three-values and aggregation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
