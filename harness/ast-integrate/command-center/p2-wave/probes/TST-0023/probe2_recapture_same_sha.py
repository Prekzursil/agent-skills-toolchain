#!/usr/bin/env python3
"""Probe 2: recapture at the same SHA reproduces SHA-ANCHORED fields exactly.

Control: untracked hook + cache file + extra branch must change sampled
counts and must not change the anchored projection. A second commit at a
new SHA must change the anchored projection.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from baseline.anchoring import anchored_projection  # noqa: E402
from baseline.capture import capture, git, git_text  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe2-recapture.raw.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0023-p2-") as td:
        root = Path(td) / "repo"
        sha1 = F.build_clean_fixture(root)
        frozen = "2026-08-24T18:00:00Z"
        snap1 = capture(root, sha1, now=frozen)

        (root / "hooks" / "untracked-hook").write_bytes(b"#!/bin/sh\necho untracked\n")
        cache = root / ".cache" / "tmp"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "blob.bin").write_bytes(b"cache-bytes\n")
        git(root, "branch", "extra-at-same-sha")

        snap2 = capture(root, sha1, now=frozen)
        proj1 = anchored_projection(snap1)
        proj2 = anchored_projection(snap2)

        F.commit_files(root, {"tracked-added.txt": b"new tracked\n"}, "second commit")
        sha2 = git_text(root, "rev-parse", "HEAD").strip()
        snap3 = capture(root, sha2, now=frozen)
        proj3 = anchored_projection(snap3)

    same_sha_equal = proj1 == proj2
    different_sha_differs = proj1 != proj3
    live_hooks_moved = snap2["hooks_live"]["count"] > snap1["hooks_live"]["count"]
    caches_moved = snap2["caches"]["count"] > snap1["caches"]["count"]
    branches_moved = snap2["branches"]["count"] > snap1["branches"]["count"]
    kind_became_sample = snap1["kind"] == "BASELINE" and snap2["kind"] == "SAMPLE"
    tracked_grew = snap3["repo"]["count"] > snap1["repo"]["count"]
    # Worktree walk would have counted the untracked hook in hooks_tree.
    tree_hooks_stable = snap1["hooks_tree"]["count"] == snap2["hooks_tree"]["count"] == 1
    reader = snap1["repo"].get("reader")

    payload = {
        "probe": "probe2-recapture-same-sha",
        "unit_id": "TST-0023",
        "sha1": sha1,
        "sha2": sha2,
        "same_sha_anchored_equal": same_sha_equal,
        "different_sha_anchored_differs": different_sha_differs,
        "live_hooks_moved": live_hooks_moved,
        "caches_moved": caches_moved,
        "branches_moved": branches_moved,
        "kind_became_sample": kind_became_sample,
        "tree_hooks_stable": tree_hooks_stable,
        "tracked_grew": tracked_grew,
        "reader": reader,
        "hooks_tree_count": snap1["hooks_tree"]["count"],
        "hooks_live_before": snap1["hooks_live"]["count"],
        "hooks_live_after": snap2["hooks_live"]["count"],
        "caches_before": snap1["caches"]["count"],
        "caches_after": snap2["caches"]["count"],
        "repo_count_sha1": snap1["repo"]["count"],
        "repo_count_sha2": snap3["repo"]["count"],
        "pass": (
            same_sha_equal
            and different_sha_differs
            and live_hooks_moved
            and caches_moved
            and branches_moved
            and kind_became_sample
            and tree_hooks_stable
            and tracked_grew
            and reader == "git-ls-tree-and-cat-file"
            and sha1 != sha2
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["pass"]:
        print("FAILED:TST-0023-probe2 recapture at the same SHA must reproduce anchored fields")
        return 1
    print(
        f"same_sha_equal=True hooks_tree={payload['hooks_tree_count']} "
        f"hooks_live {payload['hooks_live_before']}->{payload['hooks_live_after']} "
        f"kind BASELINE->SAMPLE sha2_differs=True"
    )
    print("SUCCESS:TST-0023-probe2 recapture at the same SHA reproduces anchored fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
