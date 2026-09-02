#!/usr/bin/env python3
"""Probe 1: git fsck --unreachable --dangling.

Independent of stash list/show. Recomputes the planted-blob / HEAD-blob
both-states control and the live worktree fsck census, then checks the
artifact headline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

UNIT = "AUD-0004"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    art = C.REPO / C.OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    cat = json.loads((C.REPO / "command-center/WORK-UNIT-CATALOG.json").read_text())
    unit = next(u for u in cat["work_units"] if u["id"] == UNIT)
    sentinel = str(unit.get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")

    ctl = C.fsck_both_states()
    if not ctl["ok"]:
        return fail(f"fsck both-states failed: {ctl}")
    if not ctl["fired_on_planted_blob"]:
        return fail("planted dangling blob not named by fsck")
    if not ctl["silent_on_head_blob"]:
        return fail("HEAD blob falsely listed as dangling/unreachable")
    if ctl["planted_blob"] == ctl["head_blob"]:
        return fail("planted blob sha equals HEAD blob; control is not independent")

    live = C.live_inventory()
    live_fsck = live["counts"]["live_fsck_objects"]
    worktree_git = live["discovery"]["worktree_is_git"]
    head = doc.get("headline") or {}
    inv = doc.get("inventory") or {}
    counts = inv.get("counts") or {}
    if head.get("dangling_blob_fired") is not True:
        return fail("artifact dangling_blob_fired is not true")
    if head.get("reachable_head_blob_silent") is not True:
        return fail("artifact reachable_head_blob_silent is not true")
    if head.get("live_fsck_objects") != live_fsck:
        return fail(
            f"live_fsck_objects artifact={head.get('live_fsck_objects')} recomputed={live_fsck}"
        )
    if head.get("worktree_is_git") != worktree_git:
        return fail("worktree_is_git mismatch")
    if counts.get("live_fsck_objects") != live_fsck:
        return fail("inventory.counts.live_fsck_objects mismatch")
    method = str(((doc.get("probes_methods") or {}).get("probe1") or "")).lower()
    if "fsck" not in method:
        return fail("artifact does not record probe1 as fsck")

    payload = {
        "method": "git-fsck-unreachable-dangling",
        "planted_blob": ctl["planted_blob"],
        "head_blob": ctl["head_blob"],
        "fired_on_planted_blob": True,
        "silent_on_head_blob": True,
        "live_git_repos": live["counts"]["live_git_repos"],
        "live_fsck_objects": live_fsck,
        "worktree_is_git": worktree_git,
        "command": "git fsck --unreachable --dangling",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0004-probe1 fsck unreachable/dangling; planted blob fires; "
        "HEAD blob silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
