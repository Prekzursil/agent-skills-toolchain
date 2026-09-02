#!/usr/bin/env python3
"""Probe 1: two-directional shipped-vs-live census (read-only).

Host rules/ and ~/.claude are remeasured; on this Linux worktree they are
absent. The 2026-08-09 5/88 numbers are NOT cited as today's counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare as C  # noqa: E402
import hosts as H  # noqa: E402

SHIPPED = HERE / "fixtures" / "census" / "shipped"
LIVE = HERE / "fixtures" / "census" / "live"
OUT = HERE / "probe1-two-way.raw.json"


def main() -> int:
    if not SHIPPED.is_dir() or not LIVE.is_dir():
        print("FAILED:CNF-0101-probe1 fixtures absent")
        return 1
    before_s = C.fingerprint_tree(SHIPPED)
    before_l = C.fingerprint_tree(LIVE)
    host = H.host_candidates()
    sync = H.sync_script_census()
    snap = C.compare_trees(SHIPPED, LIVE)
    after_s = C.fingerprint_tree(SHIPPED)
    after_l = C.fingerprint_tree(LIVE)
    wrote = before_s != after_s or before_l != after_l
    live_present = [
        h for h in host if h.get("role") == "live" and h["is_dir"] and h["file_count"] > 0
    ]
    shipped_present = [
        h
        for h in host
        if h.get("role") == "shipped" and h["is_dir"] and h["file_count"] > 0
    ]
    fw = snap["four_way_counts"]
    doc = {
        "host_candidates": host,
        "host_present_trees": len(live_present),
        "live_present_trees": len(live_present),
        "shipped_present_trees": len(shipped_present),
        "sync_script": sync,
        "census": snap,
        "trees_written": wrote,
        "comparison_directions": ["repo-to-live", "live-to-repo"],
        "cited_2026_08_09_5_of_88": False,
        "proof_surface": "fixture-census",
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if wrote:
        print("FAILED:CNF-0101-probe1 wrote to a compared tree")
        return 1
    if snap["union_files"] < 8:
        print("FAILED:CNF-0101-probe1 census too small")
        return 1
    if fw["identical"] < 1:
        print("FAILED:CNF-0101-probe1 no identical control")
        return 1
    if fw["eol_only"] < 1:
        print("FAILED:CNF-0101-probe1 no EOL-only class")
        return 1
    if fw["content_repo_larger"] < 1 or fw["content_live_larger"] < 1:
        print("FAILED:CNF-0101-probe1 not two-directional")
        return 1
    if fw["diverged_both_unique"] < 1:
        print("FAILED:CNF-0101-probe1 no DIVERGED both-unique pair")
        return 1
    if snap["cited_2026_08_09_5_of_88"]:
        print("FAILED:CNF-0101-probe1 cited historical 5/88")
        return 1
    missed = [
        r
        for r in snap["rows"]
        if r["class"] == "DIVERGED" and r["one_directional_class"] != "REPO_AHEAD"
    ]
    # one-directional miss is demonstrated in probe2; probe1 only requires DIVERGED exists
    _ = missed
    both_dirs = 0
    for r in snap["rows"]:
        if r["in_repo"] and r["in_live"]:
            both_dirs += 1
            if r["repo_unique_line_count"] is None or r["live_unique_line_count"] is None:
                print("FAILED:CNF-0101-probe1 missing a direction")
                return 1
    if both_dirs < 4:
        print("FAILED:CNF-0101-probe1 both-direction rows missing")
        return 1
    print(
        "host_present_trees="
        + str(len(live_present))
        + " shipped_present_trees="
        + str(len(shipped_present))
        + " union="
        + str(snap["union_files"])
        + " identical="
        + str(fw["identical"])
        + " eol_only="
        + str(fw["eol_only"])
        + " content_differ="
        + str(fw["content_differ"])
        + " content_repo_larger="
        + str(fw["content_repo_larger"])
        + " content_live_larger="
        + str(fw["content_live_larger"])
        + " diverged="
        + str(fw["diverged_both_unique"])
        + " trees_written=False"
        + " cited_2026_08_09_5_of_88=False"
        + " directions=repo-to-live,live-to-repo"
    )
    print("SUCCESS:CNF-0101-probe1 two-directional four-way census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
