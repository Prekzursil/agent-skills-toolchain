#!/usr/bin/env python3
"""Probe 2: git stash list vs git stash show --include-untracked --numstat.

Does not run fsck. An empty stash-list row and a populated one are
indistinguishable from the list alone; content is decided per entry.
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
    print(f"FAILED:{UNIT}-probe2 {msg}")
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

    ctl = C.stash_both_states()
    if not ctl["ok"]:
        return fail(f"stash both-states failed: {json.dumps(ctl)[:1500]}")
    u = ctl["untracked_pathspec"]
    if not u["saved_nothing"] or u["content_nonzero"] or u["stash_created"]:
        return fail(f"untracked pathspec did not save-nothing: {u}")
    if not ctl["empty_list_entry"]["ok"]:
        return fail("empty stash list entry not classified zero-content")
    if not ctl["tracked_stash"]["ok"] or ctl["tracked_stash"]["nonzero_count"] < 1:
        return fail("tracked stash not classified non-zero")
    flag = ctl["include_untracked_flag_needed"]
    if not flag.get("default_show_hides_untracked_only"):
        return fail(
            "untracked-only stash was visible without --include-untracked; "
            "probe 2 would be vacuous"
        )

    live = C.live_inventory()
    head = doc.get("headline") or {}
    counts = (doc.get("inventory") or {}).get("counts") or {}
    if head.get("untracked_pathspec_saved_nothing") is not True:
        return fail("artifact untracked_pathspec_saved_nothing is not true")
    if head.get("tracked_stash_nonzero") is not True:
        return fail("artifact tracked_stash_nonzero is not true")
    if head.get("empty_stash_list_entry_zero_content") is not True:
        return fail("artifact empty_stash_list_entry_zero_content is not true")
    live_nz = live["counts"]["live_stash_nonzero"]
    live_z = live["counts"]["live_stash_zero_content"]
    if head.get("live_stash_nonzero") != live_nz:
        return fail(
            f"live_stash_nonzero artifact={head.get('live_stash_nonzero')} recomputed={live_nz}"
        )
    if head.get("live_stash_zero_content") != live_z:
        return fail("live_stash_zero_content mismatch")
    if counts.get("live_stash_nonzero") != live_nz:
        return fail("inventory.counts.live_stash_nonzero mismatch")
    method = str(((doc.get("probes_methods") or {}).get("probe2") or "")).lower()
    if "stash" not in method or "include-untracked" not in method.replace("_", "-"):
        return fail("artifact does not record probe2 as stash show --include-untracked")

    payload = {
        "method": "stash-list-plus-include-untracked-numstat",
        "untracked_pathspec_saved_nothing": True,
        "untracked_stash_created": False,
        "empty_list_entry_zero_content": True,
        "tracked_stash_nonzero": True,
        "default_show_hides_untracked_only": True,
        "live_stash_nonzero": live_nz,
        "live_stash_zero_content": live_z,
        "live_git_repos": live["counts"]["live_git_repos"],
        "command": (
            "git stash list ; git stash show --include-untracked --numstat <entry>"
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0004-probe2 stash content; untracked pathspec saves nothing; "
        "tracked stash non-zero"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
