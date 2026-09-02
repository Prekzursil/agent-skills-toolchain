#!/usr/bin/env python3
"""Probe 1: mutual-wait deadlock flagged; safe twin silent (both-states).

Counts flagged vs unflagged over the live corpus as numbers. Also checks
that a namespaced Subworkflow mutual-wait is still a deadlock, and that
per-unit pipelines make cohort-hang unrepresentable while a raw barrier
does not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

OUT = HERE / "probe1-both-states.raw.json"


def main() -> int:
    reports = {r["fixture"]: r for r in C.corpus_reports()}
    mw = reports["mutual_wait.json"]
    safe = reports["safe_linear.json"]
    nested = reports["subworkflow_mutual_wait.json"]
    piped = reports["per_unit_pipelines.json"]
    hang = reports["cohort_hang.json"]

    flagged = [r for r in reports.values() if r.get("flagged")]
    unflagged = [r for r in reports.values() if not r.get("flagged")]
    flagged_count = len(flagged)
    unflagged_count = len(unflagged)

    errors: list[str] = []
    if not mw.get("methods_agree") or not safe.get("methods_agree"):
        errors.append("cycle methods disagree")
    if mw.get("verdict") != "DEADLOCK" or not mw.get("flagged"):
        errors.append(f"mutual-wait verdict={mw.get('verdict')} flagged={mw.get('flagged')}")
    if safe.get("verdict") != "CLEAN" or safe.get("flagged"):
        errors.append(f"safe-linear verdict={safe.get('verdict')} flagged={safe.get('flagged')}")
    if nested.get("verdict") != "DEADLOCK":
        errors.append(f"subworkflow mutual-wait verdict={nested.get('verdict')}")
    if piped.get("cohort_hang_representable") is not False:
        errors.append("per-unit pipelines still represent cohort hang")
    if hang.get("cohort_hang_representable") is not True:
        errors.append("raw multi-unit barrier should represent cohort hang")
    if hang.get("verdict") != "CLEAN":
        errors.append("cohort-hang fixture is not a wait-for deadlock; must stay CLEAN")
    if flagged_count < 1 or unflagged_count < 1:
        errors.append(f"both-states counts collapsed flagged={flagged_count} unflagged={unflagged_count}")

    doc = {
        "probe": "probe1-both-states",
        "unit_id": "IMP-0196",
        "flagged_count": flagged_count,
        "unflagged_count": unflagged_count,
        "flagged_ids": [r.get("workflow_id") for r in flagged],
        "unflagged_ids": [r.get("workflow_id") for r in unflagged],
        "mutual_wait": {
            "verdict": mw.get("verdict"),
            "flagged": mw.get("flagged"),
            "deadlock_nodes": mw.get("deadlock_nodes_tarjan"),
        },
        "safe_linear": {
            "verdict": safe.get("verdict"),
            "flagged": safe.get("flagged"),
        },
        "subworkflow_mutual_wait": nested.get("verdict"),
        "per_unit_pipelines_hang_representable": piped.get("cohort_hang_representable"),
        "cohort_hang_representable": hang.get("cohort_hang_representable"),
        "pass": not errors,
        "errors": errors,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"flagged_count={flagged_count} unflagged_count={unflagged_count} "
        f"mutual_wait={mw.get('verdict')} safe={safe.get('verdict')} "
        f"hang_piped={piped.get('cohort_hang_representable')} "
        f"hang_raw={hang.get('cohort_hang_representable')}"
    )
    if errors:
        print("FAILED:IMP-0196-probe1 " + "; ".join(errors))
        return 1
    print("SUCCESS:IMP-0196-probe1 mutual-wait flagged; safe fixture silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
