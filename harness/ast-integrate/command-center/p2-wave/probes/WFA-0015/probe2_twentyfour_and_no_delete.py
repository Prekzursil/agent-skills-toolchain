#!/usr/bin/env python3
"""Probe 2: 24 individual dirty-file rows, no-delete, ancestry trap.

Independent of probe 1's planted unique file. Re-builds the control estate
and requires:
  * agent-skills-toolchain has 24 dirty workflow rows, each named
  * a summariser that would collapse them is rejected
  * worktree names are identical before and after the sweep
  * squash-ahead bytes identical to origin classify PRESERVED, not unique
  * sweep.py source contains no worktree-remove / branch-delete / gc
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from estate import DIRTY_COUNT, build_estate  # noqa: E402
from sweep import PRESERVED, UNIQUE, salvage_verdict  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0015-sweep-worktrees.json"
SWEEP_SRC = HERE / "sweep.py"
FORBIDDEN = (
    "worktree remove",
    "git branch -D",
    "git gc",
    "git prune",
    "worktree prune",
)


def _summarised(rows: list) -> bool:
    return len(rows) != DIRTY_COUNT


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0015-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:WFA-0015-probe2 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:WFA-0015" not in text:
        print("FAILED:WFA-0015-probe2 sentinel absent")
        return 1

    src = SWEEP_SRC.read_text(encoding="utf-8").lower()
    for needle in FORBIDDEN:
        if needle in src:
            print(f"FAILED:WFA-0015-probe2 sweep.py contains forbidden {needle!r}")
            return 1

    with tempfile.TemporaryDirectory(prefix="wfa0015-p2-") as tmp:
        estate = build_estate(Path(tmp))
    rows = estate["rows"]
    dirty = [
        r.as_dict()
        for r in rows
        if r.worktree == "agent-skills-toolchain"
        and r.dirty
        and r.workflow_bearing
    ]
    if _summarised(dirty):
        print(
            "FAILED:WFA-0015-probe2 dirty rows summarised or missing "
            f"count={len(dirty)} want={DIRTY_COUNT}"
        )
        return 1
    rels = [r["relpath"] for r in dirty]
    if len(set(rels)) != DIRTY_COUNT:
        print("FAILED:WFA-0015-probe2 dirty relpaths not unique")
        return 1
    for row in dirty:
        if row["classification"] == PRESERVED and not row["preserved_at"]:
            print("FAILED:WFA-0015-probe2 PRESERVED without location", row)
            return 1
        if row["classification"] == UNIQUE and row["preserved_at"]:
            print("FAILED:WFA-0015-probe2 UNIQUE with location", row)
            return 1
    preserved_n = sum(1 for r in dirty if r["classification"] == PRESERVED)
    unique_n = sum(1 for r in dirty if r["classification"] == UNIQUE)
    if preserved_n < 1 or unique_n < 1:
        print("FAILED:WFA-0015-probe2 dirty set is not mixed", preserved_n, unique_n)
        return 1

    if estate["worktree_names_before"] != estate["worktree_names_after"]:
        print("FAILED:WFA-0015-probe2 worktree set mutated")
        return 1
    if estate["deletions_performed"]:
        print("FAILED:WFA-0015-probe2 deletions_performed not empty")
        return 1

    ahead = estate["ahead_rows"]
    if not ahead:
        print("FAILED:WFA-0015-probe2 squash-ahead rows missing")
        return 1
    if any(r["classification"] != PRESERVED for r in ahead):
        print("FAILED:WFA-0015-probe2 squash-ahead not PRESERVED", ahead)
        return 1
    if any(not r["preserved_at"] for r in ahead):
        print("FAILED:WFA-0015-probe2 squash-ahead PRESERVED without location")
        return 1

    art_dirty = doc.get("agent_skills_toolchain_dirty_files") or []
    if len(art_dirty) != DIRTY_COUNT:
        print(
            "FAILED:WFA-0015-probe2 artifact dirty list summarised "
            f"n={len(art_dirty)}"
        )
        return 1

    salvage = {
        wt: salvage_verdict(wt, rows)
        for wt in (
            "agent-skills-toolchain",
            "ast-harness-reconcile",
            "ast-statusline-capture",
            "cookie-bridge-skill",
            "ast-increment1",
        )
    }
    if salvage["ast-harness-reconcile"]["verdict"] != "CONTENT-PRESERVED-ELSEWHERE":
        print("FAILED:WFA-0015-probe2 reconcile should be preserved-elsewhere")
        return 1
    if salvage["cookie-bridge-skill"]["verdict"] != "CONTENT-PRESERVED-ELSEWHERE":
        print("FAILED:WFA-0015-probe2 cookie-bridge should be preserved-elsewhere")
        return 1
    for wt in (
        "agent-skills-toolchain",
        "ast-statusline-capture",
        "ast-increment1",
    ):
        if salvage[wt]["verdict"] != "SALVAGEABLE-UNIQUE-WORKFLOW":
            print(f"FAILED:WFA-0015-probe2 {wt} should be salvageable", salvage[wt])
            return 1
        if salvage[wt]["delete_recommended"]:
            print(f"FAILED:WFA-0015-probe2 {wt} delete_recommended true")
            return 1

    payload = {
        "pass": True,
        "probe": "probe2-twentyfour-and-no-delete",
        "unit_id": "WFA-0015",
        "dirty_count": len(dirty),
        "dirty_relpaths": rels,
        "preserved_dirty": preserved_n,
        "unique_dirty": unique_n,
        "worktrees_unchanged": True,
        "squash_ahead_all_preserved": True,
        "salvage": {k: v["verdict"] for k, v in salvage.items()},
        "forbidden_ops_absent": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"dirty={len(dirty)} preserved={preserved_n} unique={unique_n} "
        "worktrees_unchanged=1 squash_ahead=PRESERVED"
    )
    print(
        "SUCCESS:WFA-0015-probe2 24 dirty files classified individually; "
        "no worktree removed; squash-ahead is PRESERVED by content"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
