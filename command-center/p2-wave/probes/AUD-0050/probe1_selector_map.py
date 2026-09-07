#!/usr/bin/env python3
"""AUD-0050 NAMED PROBE 1: map each test path to CI steps whose selector would collect it.

Control: planted orphan outside every selector MUST appear in the orphan list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_map_lib as G  # noqa: E402

OUT_JSON = G.PROBE / "probe1-selector-map.json"
OUT_RAW = G.PROBE / "probe1-selector-map.raw.txt"


def main() -> int:
    G.ast_selfcheck()
    tests = G.inventory_test_files()
    steps = G.extract_ci_pytest_steps()

    rows: list[dict] = []
    orphan: list[str] = []
    covered: list[str] = []
    for t in tests:
        matching: list[str] = []
        for step in steps:
            hit = False
            for inv in step["invocations"]:
                if G.path_covered_by_selector(t, inv):
                    hit = True
                    break
            if hit:
                matching.append(step["step_id"])
        entry = {"path": t, "matching_steps": matching, "step_count": len(matching)}
        rows.append(entry)
        if matching:
            covered.append(t)
        else:
            orphan.append(t)

    planted_is_orphan = G.PLANTED_ORPHAN in orphan
    # Discrimination control: if we strip the planted path from orphans artificially,
    # empty-orphan would be the bad state — here we require planted present.
    control_ok = planted_is_orphan and len(orphan) >= 1

    # Compact map for the receipt: keep full rows but also summary indexes
    by_step: dict[str, list[str]] = {}
    for r in rows:
        for sid in r["matching_steps"]:
            by_step.setdefault(sid, []).append(r["path"])

    doc = {
        "unit": "AUD-0050",
        "probe": 1,
        "ok": control_ok,
        "test_file_count": len(tests),
        "ci_pytest_step_count": len(steps),
        "covered_count": len(covered),
        "orphan_count": len(orphan),
        "planted_orphan": G.PLANTED_ORPHAN,
        "planted_is_orphan": planted_is_orphan,
        "control_ok": control_ok,
        "orphan_paths": orphan,
        "steps": [
            {
                "step_id": s["step_id"],
                "workflow": s["workflow"],
                "job": s["job"],
                "step_index": s["step_index"],
                "name": s["name"],
                "working_directory": s["working_directory"],
                "invocation_count": len(s["invocations"]),
                "selector_paths": sorted(
                    {p for inv in s["invocations"] for p in inv["paths"]}
                ),
                "selector_ignores": sorted(
                    {p for inv in s["invocations"] for p in inv["ignores"]}
                ),
            }
            for s in steps
        ],
        "coverage_rows": rows,
        "files_by_step": {k: v for k, v in sorted(by_step.items())},
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0050 NAMED PROBE 1: test-path → CI-selector coverage map",
        "unit=AUD-0050",
        f"test_file_count={len(tests)}",
        f"ci_pytest_step_count={len(steps)}",
        f"covered_count={len(covered)}",
        f"orphan_count={len(orphan)}",
        f"planted_orphan={G.PLANTED_ORPHAN}",
        f"planted_is_orphan={planted_is_orphan}",
        f"control_ok={control_ok}",
        "ORPHAN_SAMPLE:",
    ]
    for p in orphan[:40]:
        lines.append(f"  {p}")
    if len(orphan) > 40:
        lines.append(f"  ... ({len(orphan) - 40} more)")
    lines.append(
        "SUCCESS:AUD-0050-probe1"
        if control_ok
        else "FAIL:AUD-0050-probe1 planted orphan not in orphan list (mapper not discriminating)"
    )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if control_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
