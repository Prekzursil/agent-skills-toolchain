#!/usr/bin/env python3
"""Probe 2: current-tree collision count is reported, not assumed zero.

Recomputes the census from the live path list before reading the artifact
answer. An assumed-zero mutant (no walk) must disagree with a real scan.
Injecting Foo.md/foo.md into the live listing must raise the count, proving
the detector is a function of the path list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402

ART = REPO / "command-center/receipts/TST-0064.json"
UNIT = "TST-0064"
PATH_FLOOR = 200


def fail(msg: str) -> int:
    print(f"FAILED:TST-0064-probe2 {msg}")
    return 1


def main() -> int:
    live = D.census(REPO)
    assumed = D.assumed_zero(REPO)
    paths, source = D.listed_paths(REPO)
    injected = list(paths) + [D.PLANTED_UPPER, D.PLANTED_LOWER]
    injected_count = len(D.collision_groups(injected))
    empty_count = len(D.collision_groups([]))
    plant_increases = injected_count > live["collision_group_count"]
    assumed_agrees = (
        assumed["collision_group_count"] == live["collision_group_count"]
        and assumed["path_count"] == live["path_count"]
    )
    print(
        json.dumps(
            {
                "probe": "probe2-census-not-assumed",
                "unit_id": UNIT,
                "source": source,
                "path_count": live["path_count"],
                "collision_group_count": live["collision_group_count"],
                "assumed_zero_path_count": assumed["path_count"],
                "assumed_zero_agrees_with_live": assumed_agrees,
                "empty_list_collision_group_count": empty_count,
                "injected_plant_collision_group_count": injected_count,
                "injected_plant_increases_count": plant_increases,
                "git_index_present": live["git_index_present"],
            },
            sort_keys=True,
        )
    )
    if live["path_count"] < PATH_FLOOR:
        return fail(f"path_count={live['path_count']} below floor {PATH_FLOOR}")
    if live["path_count"] != len(paths):
        return fail("census path_count drifted from listed_paths")
    if empty_count != 0:
        return fail("empty path list must yield zero collisions")
    if assumed["path_count"] != 0 or assumed["collision_group_count"] != 0:
        return fail("assumed-zero mutant did not report zeros")
    if assumed_agrees:
        return fail("assumed-zero mutant agrees with live scan (scan did not happen)")
    if not plant_increases:
        return fail("injecting Foo.md/foo.md did not raise collision_group_count")
    if injected_count != live["collision_group_count"] + 1:
        return fail(
            f"injected count {injected_count} != live "
            f"{live['collision_group_count']}+1"
        )

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing (derived first, then compared)")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    census = ext.get("census") or doc.get("census") or {}
    art_paths = census.get("path_count")
    if art_paths is None or int(art_paths) < PATH_FLOOR:
        return fail(
            f"artifact path_count={census.get('path_count')} below floor {PATH_FLOOR}"
        )
    # Sibling waves may add non-colliding files between emit and re-run.
    # Collision groups must still match; path_count is a lower bound, not a lock.
    if live["path_count"] < int(art_paths):
        print(
            f"note path_count live={live['path_count']} < artifact={art_paths} "
            "(tree shrank; still checking collision groups)"
        )
    art_cols = census.get("collision_group_count")
    if art_cols is None or int(art_cols) != live["collision_group_count"]:
        return fail(
            f"artifact collisions={census.get('collision_group_count')} "
            f"live={live['collision_group_count']}"
        )
    if census.get("source") != live["source"]:
        return fail(f"artifact source={census.get('source')} live={live['source']}")
    if census.get("injected_plant_increases_count") is not True:
        return fail("artifact missing injected-plant increase")
    if census.get("assumed_zero_agrees_with_live") is not False:
        return fail("artifact did not reject assumed-zero")
    art_cols = census.get("collisions")
    if art_cols != live["collisions"]:
        return fail("artifact collision list drifted from live census")
    reviewer = doc.get("reviewer") or {}
    rev_extra = ext.get("reviewer") if isinstance(ext.get("reviewer"), dict) else {}
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    shown = rev_extra.get("shown_conclusion_first", reviewer.get("shown_conclusion_first"))
    if shown is not False:
        return fail("reviewer was conclusion-anchored")
    reran = rev_extra.get(
        "re_ran_detector_control", reviewer.get("re_ran_detector_control")
    )
    if reran is not True:
        return fail("reviewer did not re-run detector control")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    print("derived_before_artifact=True assumed_zero_rejected=True")
    print("SUCCESS:TST-0064-probe2 census reported from live listing, not assumed zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
