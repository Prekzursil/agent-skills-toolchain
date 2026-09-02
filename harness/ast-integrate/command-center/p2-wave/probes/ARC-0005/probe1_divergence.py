#!/usr/bin/env python3
"""Probe 1: live-vs-repo divergence with sha256 AND byte-size (two signals).

Does not cite the 2026-08-09 5/88 numbers. Remeasures host rules/ versus
~/.claude/rules today, and the generated two-directional census fixtures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trees as T  # noqa: E402

OUT = HERE / "probe1-divergence.raw.json"


def main() -> int:
    host = T.host_candidates()
    host_div = T.host_divergence()
    snap = T.build_census_fixtures()
    T.dump(
        OUT,
        {
            "host_candidates": host,
            "host_divergence": host_div,
            "census": snap,
        },
    )
    if snap["union_files"] < 8:
        print("FAILED:ARC-0005-probe1 census too small")
        return 1
    if snap["repo_larger"] < 1 or snap["live_larger"] < 1:
        print("FAILED:ARC-0005-probe1 not two-directional")
        return 1
    if snap["identical"] < 1:
        print("FAILED:ARC-0005-probe1 no identical control files")
        return 1
    if snap["cited_2026_08_09_5_of_88"] or host_div["cited_2026_08_09_5_of_88"]:
        print("FAILED:ARC-0005-probe1 cited historical 5/88")
        return 1
    sha_rows = [r for r in snap["rows"] if "repo_sha256" in r and "live_sha256" in r]
    size_rows = [r for r in snap["rows"] if "repo_bytes" in r and "live_bytes" in r]
    if len(sha_rows) < 4 or len(size_rows) < 4:
        print("FAILED:ARC-0005-probe1 missing second signal")
        return 1
    host_rows = host_div.get("rows") or []
    if host_div["repo_tree_present"] and len(host_rows) < 8:
        print("FAILED:ARC-0005-probe1 host repo rules not hashed")
        return 1
    host_sha = [r for r in host_rows if "repo_sha256" in r or "live_sha256" in r]
    host_sz = [r for r in host_rows if "repo_bytes" in r or "live_bytes" in r]
    if host_div["repo_tree_present"] and (len(host_sha) < 8 or len(host_sz) < 8):
        print("FAILED:ARC-0005-probe1 host census missing second signal")
        return 1
    print(
        "host_repo_present="
        + str(host_div["repo_tree_present"])
        + " host_live_present="
        + str(host_div["live_tree_present"])
        + " host_union="
        + str(host_div["union_files"])
        + " host_identical="
        + str(host_div["identical"])
        + " host_repo_only="
        + str(host_div["repo_only"])
        + " host_live_only="
        + str(host_div["live_only"])
        + " fixture_union="
        + str(snap["union_files"])
        + " identical="
        + str(snap["identical"])
        + " repo_larger="
        + str(snap["repo_larger"])
        + " live_larger="
        + str(snap["live_larger"])
        + " sha_diff_same_size="
        + str(snap["sha_diff_same_size"])
        + " repo_only="
        + str(snap["repo_only"])
        + " live_only="
        + str(snap["live_only"])
        + " cited_2026_08_09_5_of_88=False"
        + " signals=sha256,byte-size"
    )
    print("SUCCESS:ARC-0005-probe1 two-signal divergence census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
