#!/usr/bin/env python3
"""Probe 1: git status --porcelain=v2 --untracked-files=all per worktree.

Live host is scanned first (honest absence). Fixture recreation of the six
named surviving trees is then enumerated so the porcelain parser is shown
to discriminate a dirty tree from a clean one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

ART = REPO / "command-center/audit/AUD-0002-worktree-inventory.json"
RAW = HERE / "probe1-porcelain.raw.json"
SENTINEL = (
    "SUCCESS:AUD-0002 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
SURVIVING_NAMES = [s["name"] for s in I.SURVIVING]


def domain(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    host = (
        doc.get("live_host")
        or report.get("live_host")
        or ext.get("live_host")
        or {}
    )
    inventory = (
        doc.get("inventory")
        or report.get("inventory")
        or ext.get("inventory")
        or []
    )
    return {"live_host": host, "inventory": inventory}


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0002-probe1 {msg}")
    return 1


def main() -> int:
    live = I.live_host_scan()
    trees = I.build_fixtures()
    surfaces = []
    for name, root in trees.items():
        dirty = I.dirty_surface(root)
        origin, origin_rc, origin_raw = I.origin_url(root)
        surfaces.append(
            {
                "name": name,
                "path": str(root),
                "origin_url": origin,
                "origin_exit_code": origin_rc,
                "origin_raw": origin_raw,
                "porcelain_exit_code": dirty["exit_code"],
                "porcelain_raw": dirty["raw"],
                "dirty_tracked": dirty["dirty_tracked"],
                "dirty_untracked": dirty["dirty_untracked"],
                "entry_count": len(dirty["entries"]),
            }
        )

    dirty_trees = [s for s in surfaces if s["entry_count"] > 0]
    clean_trees = [s for s in surfaces if s["entry_count"] == 0]
    parse_ok = all(s["porcelain_exit_code"] == 0 for s in surfaces)
    identities = {s["name"]: s["origin_url"] for s in surfaces}

    payload = {
        "live_git_worktree": live["git_worktree"],
        "live_named_present": live["named_surviving_present"],
        "live_named_absent": live["named_surviving_absent"],
        "live_porcelain_exit_code": live["porcelain_exit_code"],
        "live_porcelain_raw": live["porcelain_raw"],
        "live_worktree_list_raw": live["worktree_list_raw"],
        "fixture_tree_count": len(surfaces),
        "fixture_dirty_trees": [s["name"] for s in dirty_trees],
        "fixture_clean_trees": [s["name"] for s in clean_trees],
        "identities": identities,
        "surfaces": surfaces,
        "pass": False,
    }

    if not parse_ok:
        I.dump_json(RAW, payload)
        return fail("porcelain exited non-zero on a fixture worktree")
    if len(surfaces) != 6:
        I.dump_json(RAW, payload)
        return fail(f"fixture tree count {len(surfaces)} want 6")
    if not dirty_trees:
        I.dump_json(RAW, payload)
        return fail("porcelain reported zero dirty trees; detector is not discriminating")
    if not clean_trees:
        I.dump_json(RAW, payload)
        return fail("no clean fixture tree; detector is not discriminating")
    if identities.get("ast-integrate") != identities.get("agent-skills-toolchain"):
        I.dump_json(RAW, payload)
        return fail("ast-integrate origin does not match agent-skills-toolchain")
    if identities.get("ast-increment1") == identities.get("agent-skills-toolchain"):
        I.dump_json(RAW, payload)
        return fail("distinct-repo identity collapsed to the toolchain origin")
    if live["git_worktree"] is True:
        # Unexpected on this host; still allow if porcelain ran, but do not
        # pretend the historical six were found unless named_present says so.
        pass

    if not ART.is_file() or ART.stat().st_size <= 0:
        I.dump_json(RAW, payload)
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        I.dump_json(RAW, payload)
        return fail("artifact missing completion sentinel")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        I.dump_json(RAW, payload)
        return fail(f"self-declared {doc.get('state')}")
    blob = domain(doc)
    host = blob["live_host"]
    if host.get("git_worktree") is not live["git_worktree"]:
        I.dump_json(RAW, payload)
        return fail("artifact live_host.git_worktree drifted from this scan")
    names = [r.get("name") for r in blob["inventory"] if isinstance(r, dict)]
    missing = [s for s in SURVIVING_NAMES if s not in names]
    if missing:
        I.dump_json(RAW, payload)
        return fail(f"artifact inventory missing {missing}")

    payload["pass"] = True
    I.dump_json(RAW, payload)
    print(
        json.dumps(
            {
                "live_git_worktree": live["git_worktree"],
                "live_named_present": live["named_surviving_present"],
                "fixture_trees": len(surfaces),
                "dirty": [s["name"] for s in dirty_trees],
                "clean": [s["name"] for s in clean_trees],
                "identities": identities,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:AUD-0002-probe1 porcelain v2 dirty-surface per worktree; "
        "clean vs dirty discriminated; origin identity recorded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
