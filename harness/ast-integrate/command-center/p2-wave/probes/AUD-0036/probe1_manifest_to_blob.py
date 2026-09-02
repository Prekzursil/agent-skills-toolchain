#!/usr/bin/env python3
"""Probe 1: manifest-to-disk plus sha256 of committed blob via git cat-file -p."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0036/probe1_manifest_to_blob.py"
)


def main() -> int:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    snap = E.snapshot()
    dual = snap["hash_control"]
    live = snap["live_git"]
    man = snap["manifest"]
    m2d = snap["manifest_to_disk"]
    contracted = snap["contracted_inventory"]
    slim = {
        "probe": "probe1-manifest-to-blob",
        "unit_id": E.UNIT,
        "command": P1,
        "blob_route": E.BLOB_ROUTE,
        "live_git": {
            "rev_parse_inside": live["rev_parse_inside"],
            "dot_git_exists": live["dot_git_exists"],
            "blob_route_live": live["blob_route_live"],
        },
        "manifest_present": man["present"],
        "manifest_entry_count": man["entry_count"],
        "named_missing_count": m2d["named_missing_count"],
        "hash_mismatch_vs_blob_count": m2d["hash_mismatch_vs_blob_count"],
        "contracted_present_on_disk": contracted["present_on_disk"],
        "contracted_missing_on_disk": contracted["missing_on_disk"],
        "contracted_missing_paths": contracted["missing_paths"],
        "hash_control": {
            "control_pass": dual["control_pass"],
            "known_file": dual["known_file"],
            "worktree_sha256_raw": dual["worktree_sha256_raw"],
            "worktree_sha256_lf": dual["worktree_sha256_lf"],
            "blob_sha256": dual["blob_sha256"],
            "blob_command": dual.get("blob_command"),
            "blob_route": dual["blob_route"],
            "manifest_matches": dual["manifest_matches"],
            "manifest_matches_blob": dual["manifest_matches_blob"],
            "manifest_matches_worktree_raw": dual["manifest_matches_worktree_raw"],
            "reach6_crlf_raw_differs_from_blob": dual["reach6_crlf_raw_differs_from_blob"],
            "both_values_recorded": dual["both_values_recorded"],
        },
        "pass": bool(dual["control_pass"]),
    }
    print(json.dumps(slim, sort_keys=True))
    if not dual["control_pass"]:
        print("FAILED:AUD-0036-probe1 dual-route blob/worktree control")
        return 1
    if dual["worktree_sha256_raw"] == dual["blob_sha256"]:
        print("FAILED:AUD-0036-probe1 worktree_raw unexpectedly equals blob")
        return 1
    if dual["manifest_matches"] != "blob":
        print("FAILED:AUD-0036-probe1 manifest did not match blob route")
        return 1
    print(
        "SUCCESS:AUD-0036-probe1 "
        f"manifest_present={man['present']} entries={man['entry_count']} "
        f"named_missing={m2d['named_missing_count']} "
        f"blob_sha256={dual['blob_sha256'][:12]} "
        f"worktree_raw={dual['worktree_sha256_raw'][:12]} "
        f"manifest_matches={dual['manifest_matches']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
