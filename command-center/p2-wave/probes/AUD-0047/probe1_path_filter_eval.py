#!/usr/bin/env python3
"""AUD-0047 NAMED PROBE 1: evaluate path filters against each gate's protected files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from path_filter_lib import evaluate_workflow

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-path-filter-eval.json"
OUT_RAW = PROBE / "probe1-path-filter-eval.raw.txt"

CATALOG_VERBATIM = (
    "Probe 1: evaluate each filter pattern against the gate's protected file list."
)


def main() -> int:
    workflows = sorted((REPO / ".github" / "workflows").glob("*.yml"))
    rows = []
    live_hole_count = 0
    filtered_workflow_count = 0
    for wf in workflows:
        rel = wf.relative_to(REPO)
        row = evaluate_workflow(rel)
        # re-evaluate with absolute path resolution from REPO
        row = evaluate_workflow(REPO / rel)
        row["workflow"] = rel.as_posix()
        rows.append(row)
        if row["has_path_filters"]:
            filtered_workflow_count += 1
            live_hole_count += row["hole_count"]

    planted_wf = PROBE / "fixtures" / "planted-paths-ignore" / "workflow.yml"
    planted_pf = (
        (PROBE / "fixtures" / "planted-paths-ignore" / "protected_files.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    planted_pf = [p.strip() for p in planted_pf if p.strip()]
    planted = evaluate_workflow(planted_wf, protected_override=planted_pf)
    planted["workflow"] = (
        "command-center/p2-wave/probes/AUD-0047/fixtures/planted-paths-ignore/workflow.yml"
    )
    planted_miss_caught = planted["hole_count"] > 0 and any(
        h["protected_file"] == "command-center/receipt_validate.py"
        for h in planted["holes"]
    )

    payload = {
        "unit": "AUD-0047",
        "catalog_verbatim": CATALOG_VERBATIM,
        "workflows_scanned": len(rows),
        "filtered_workflow_count": filtered_workflow_count,
        "live_hole_count": live_hole_count,
        "live_workflows": rows,
        "planted": planted,
        "planted_miss_caught": planted_miss_caught,
        "ok": planted_miss_caught,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0047 NAMED PROBE 1: path-filter vs protected-file evaluation",
        f"catalog_verbatim={CATALOG_VERBATIM}",
        "unit=AUD-0047",
        f"workflows_scanned={len(rows)}",
        f"filtered_workflow_count={filtered_workflow_count}",
        f"live_hole_count={live_hole_count}",
        f"planted_miss_caught={planted_miss_caught}",
        f"planted_hole_count={planted['hole_count']}",
        "PLANTED-HOLES-BEGIN",
    ]
    for h in planted["holes"]:
        lines.append(f"PLANTED\t{h['protected_file']}\t{h['event']}\t{h['reason']}")
    lines.append("PLANTED-HOLES-END")
    lines.append("LIVE-HOLES-BEGIN")
    for row in rows:
        for h in row["holes"]:
            lines.append(
                f"LIVE\t{row['workflow']}\t{h['protected_file']}\t{h['event']}\t{h['reason']}"
            )
    lines.append("LIVE-HOLES-END")
    lines.append(
        "SUCCESS:AUD-0047-probe1" if planted_miss_caught else "FAIL:AUD-0047-probe1"
    )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if planted_miss_caught else 1


if __name__ == "__main__":
    raise SystemExit(main())
