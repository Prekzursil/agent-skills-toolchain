#!/usr/bin/env python3
"""Probe 1: dry-run repair plan vs independent differ (exact set match).

Signal 1: repair dry-run would_touch set and per-file classification.
Signal 2: independent comm-style differ over the same trees.
Any planned touch classified DIVERGED by the differ fails the unit.
Also independently classifies a 10-file sample by reading both sides.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from plugin.drift import DIVERGED, REPAIRABLE, classify_pair  # noqa: E402
from plugin.independent_differ import classify_pair_independent  # noqa: E402
from plugin.repair import apply_repair, iter_rel_files  # noqa: E402
import scenario as S  # noqa: E402

OUT = HERE / "probe1-dry-run.raw.json"


def read_opt(path: Path | None) -> bytes | None:
    if path is None:
        return None
    return path.read_bytes()


def main() -> int:
    meta = S.build_fixtures()
    repo, live = S.estate_roots()
    host = S.host_candidates()
    host_present = [h for h in host if h["is_dir"] and h["file_count"] > 0]

    plan = apply_repair(repo, live, one_directional=False, dry_run=True)
    repo_files = iter_rel_files(repo)
    live_files = iter_rel_files(live)
    keys = sorted(set(repo_files) | set(live_files))

    indep: dict[str, dict] = {}
    mismatch: list[dict] = []
    for rel in keys:
        rec = classify_pair_independent(
            read_opt(repo_files.get(rel)),
            read_opt(live_files.get(rel)),
        )
        indep[rel] = rec
        tool = plan["classifications"][rel]
        if rec["classification"] != tool:
            mismatch.append(
                {
                    "path": rel,
                    "repair": tool,
                    "independent": rec["classification"],
                }
            )

    touch = set(plan["touch_set"])
    indep_repairable = {
        rel for rel, rec in indep.items() if rec["classification"] in REPAIRABLE
    }
    diverged_in_plan = [
        rel
        for rel in touch
        if indep.get(rel, {}).get("classification") == DIVERGED
        or plan["classifications"].get(rel) == DIVERGED
    ]

    sample_rows = []
    sample_fail = []
    for rel in meta["reviewer_sample"]:
        rb = read_opt(repo_files.get(rel))
        lb = read_opt(live_files.get(rel))
        tool = classify_pair(rb, lb)
        rec = classify_pair_independent(rb, lb)
        row = {
            "path": rel,
            "repair": tool,
            "independent": rec["classification"],
            "live_unique": rec.get("live_unique_lines") or [],
            "repo_unique": rec.get("repo_unique_lines") or [],
        }
        sample_rows.append(row)
        if tool != rec["classification"]:
            sample_fail.append(row)

    by_class: dict[str, list[str]] = {}
    for rel, klass in plan["classifications"].items():
        by_class.setdefault(klass, []).append(rel)
    expected = meta["expected"]
    expected_fail = []
    for klass, paths in expected.items():
        got = set(by_class.get(klass, []))
        want = set(paths)
        if got != want:
            expected_fail.append(
                {
                    "class": klass,
                    "missing": sorted(want - got),
                    "extra": sorted(got - want),
                }
            )

    payload = {
        "host_candidates": host,
        "host_present": host_present,
        "dry_run_over": "planted-estate" if not host_present else "host-and-estate",
        "cited_historical_5_of_88": False,
        "union_files": plan["union_files"],
        "touch_set": sorted(touch),
        "independent_repairable": sorted(indep_repairable),
        "set_match": touch == indep_repairable,
        "classification_mismatches": mismatch,
        "diverged_in_plan": diverged_in_plan,
        "reviewer_sample": sample_rows,
        "expected_fail": expected_fail,
        "by_class_counts": {k: len(v) for k, v in sorted(by_class.items())},
        "plan_refused": plan["refused"],
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if mismatch:
        print("FAILED:IMP-0025-probe1 classification mismatch", mismatch[:8])
        return 1
    if touch != indep_repairable:
        print(
            "FAILED:IMP-0025-probe1 set mismatch "
            f"touch={sorted(touch)} indep={sorted(indep_repairable)}"
        )
        return 1
    if diverged_in_plan:
        print("FAILED:IMP-0025-probe1 DIVERGED in repair plan", diverged_in_plan)
        return 1
    if sample_fail:
        print("FAILED:IMP-0025-probe1 reviewer sample disagree", sample_fail)
        return 1
    if len(sample_rows) != 10:
        print(f"FAILED:IMP-0025-probe1 reviewer sample size {len(sample_rows)}")
        return 1
    if expected_fail:
        print("FAILED:IMP-0025-probe1 planted class census", expected_fail)
        return 1
    if not any(plan["classifications"][r] == DIVERGED for r in S.DIVERGED):
        print("FAILED:IMP-0025-probe1 planted DIVERGED not classified")
        return 1
    if any(rel in touch for rel in S.DIVERGED):
        print("FAILED:IMP-0025-probe1 would touch planted DIVERGED")
        return 1
    if any(rel in touch for rel in S.LIVE_AHEAD):
        print("FAILED:IMP-0025-probe1 would touch LIVE-AHEAD")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-dry-run-vs-differ",
                "unit_id": "IMP-0025",
                "union_files": plan["union_files"],
                "touch": len(touch),
                "set_match": True,
                "diverged_in_plan": 0,
                "reviewer_sample": 10,
                "host_present_trees": len(host_present),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"set_match=True diverged_in_plan=0 reviewer=10 host_present={len(host_present)}"
    )
    print("SUCCESS:IMP-0025-probe1 dry-run plan matches independent differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
