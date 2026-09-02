#!/usr/bin/env python3
"""Probe 1: three-run variance and two-size curve (workflow on_error field)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402
from scale import TARGET, analogue_skill_count, expected_file_count  # noqa: E402

COST = REPO / "command-center/phase3/A2/COST.json"


def _fail(msg: str) -> int:
    print(f"FAILED:ARC-0011-probe1 {msg}")
    return 1


def main() -> int:
    result = M.campaign(mutate="workflow_on_error", timer_name="perf_counter")
    if len(result["sizes"]) != 2:
        return _fail("need two catalogue sizes")
    if not result["claim_valid"]:
        return _fail(f"spread {result['max_spread']:.3f} exceeds 0.30")
    n_skill = analogue_skill_count()
    for row in result["sizes"]:
        expect = expected_file_count(
            row["workflows"], row["protocols"], row["presets"], n_skill
        )
        print(
            f"size {row['label']} files_full={row['full_file_writes']} "
            f"files_incr={row['incremental_file_writes']} "
            f"full_median_s={row['full_pipeline']['median_s']:.6f} "
            f"spread={row['full_pipeline']['spread']:.4f}"
        )
        if row["full_file_writes"] != expect:
            return _fail(f"file formula {row['full_file_writes']} != {expect}")
        if row["incremental_file_writes"] != 2:
            return _fail("incremental write count is not 2")
        if not row["incremental_bytes_match_full_for_dirty_paths"]:
            return _fail("incremental bytes != full bytes for dirty paths")
        if min(len(row["full_pipeline"]["runs_s"]), 3) < 3:
            return _fail("need three full-pipeline runs")
    target = next(s for s in result["sizes"] if s["label"] == "target")
    expect_t = expected_file_count(
        TARGET["workflows"], TARGET["protocols"], TARGET["presets"], n_skill
    )
    if target["full_file_writes"] != expect_t:
        return _fail("target file count mismatch")
    if COST.is_file():
        doc = json.loads(COST.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"COST.json state={doc.get('state')}")
        baked = (doc.get("measurements") or {}).get("probe1") or {}
        baked_sizes = baked.get("sizes") or []
        if len(baked_sizes) != 2:
            return _fail("COST.json missing probe1 sizes")
        live_files = [s["full_file_writes"] for s in result["sizes"]]
        baked_files = [s["full_file_writes"] for s in baked_sizes]
        if live_files != baked_files:
            return _fail(f"COST file-write drift {baked_files} vs {live_files}")
        for live, baked_row in zip(result["sizes"], baked_sizes):
            ta = live["full_pipeline"]["median_s"]
            tb = baked_row["full_pipeline"]["median_s"]
            if abs(ta - tb) / max(ta, tb, 1e-9) > M.SPREAD_LIMIT:
                return _fail(f"COST median drift {tb:.6f} vs live {ta:.6f}")
        text = COST.read_text(encoding="utf-8")
        if "SUCCESS:ARC-0011" not in text:
            return _fail("sentinel absent")
    print(
        f"max_spread={result['max_spread']:.4f} "
        f"crossover_reached={result['crossover_reached_at_target']}"
    )
    print("SUCCESS:ARC-0011-probe1 three-run variance and two-size curve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
