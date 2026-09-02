#!/usr/bin/env python3
"""Probe 2: cycle test + live-capability negative control.

Mechanically different from probe 1: this builds two isolated fixture
graphs (a two-node cycle and a live-only tree) plus a dead-target tree,
then asserts graph properties. It does not depend on the repo skills/
census that probe 1 uses as the real-tombstone sample.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.tombstones import (  # noqa: E402
    CYCLE,
    DEAD,
    LIVE,
    DeadSelectionError,
    Root,
    discover,
    index_from_records,
    is_tombstone,
    resolve,
    route_selection,
    tombstone_table,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0405-probe2 {msg}")
    return 1


def root_for(name: str) -> Root:
    return Root(f"fixture-{name}", HERE / "fixtures" / "trees" / name / "skills", "skill")


def load(name: str):
    live, tombs = discover([root_for(name)], repo=REPO)
    live_ids, by_old = index_from_records(live, tombs)
    return live, tombs, live_ids, by_old


def main() -> int:
    c_live, c_tombs, c_ids, c_by = load("cycle")
    c_table = tombstone_table(c_live, c_tombs)
    print(json.dumps({"cycle_table": c_table, "cycle_live": [x.capability_id for x in c_live]}, sort_keys=True))
    if len(c_tombs) < 2:
        return fail(f"cycle fixture tombstones={len(c_tombs)} want 2")
    for old in ("skill.loop-a", "skill.loop-b"):
        result = resolve(old, c_ids, c_by)
        if result.status != CYCLE or result.defect != "tombstone-cycle":
            return fail(
                f"{old} status={result.status} defect={result.defect} "
                f"want CYCLE/tombstone-cycle hops={result.hops}"
            )
        if result.terminal_id is not None:
            return fail(f"{old} cycle produced terminal_id={result.terminal_id}")
        try:
            route_selection(old, c_ids, c_by)
        except DeadSelectionError:
            pass
        else:
            return fail(f"{old} cycle was injectable as a selection")

    d_live, d_tombs, d_ids, d_by = load("dead")
    d_table = tombstone_table(d_live, d_tombs)
    print(json.dumps({"dead_table": d_table}, sort_keys=True))
    dead = resolve("skill.orphan-old", d_ids, d_by)
    if dead.status != DEAD or dead.defect != "missing-target":
        return fail(
            f"missing target classified as {dead.status}/{dead.defect} "
            "instead of DEAD/missing-target (would be a note, not a defect)"
        )
    if any(r.get("resolution") == "RESOLVED" for r in d_table):
        return fail("dead-target row marked RESOLVED")
    try:
        route_selection("skill.orphan-old", d_ids, d_by)
    except DeadSelectionError:
        pass
    else:
        return fail("dead target was injectable as a selection")

    n_live, n_tombs, n_ids, n_by = load("live-control")
    print(
        json.dumps(
            {
                "negative_live": [x.capability_id for x in n_live],
                "negative_tombs": [t.old_id for t in n_tombs],
            },
            sort_keys=True,
        )
    )
    if n_tombs:
        return fail(
            f"live capability treated as tombstone: {[t.old_id for t in n_tombs]}"
        )
    if "skill.never-tombstoned" not in n_ids:
        return fail("negative-control live id missing from live set")
    if is_tombstone("skill.never-tombstoned", n_by):
        return fail("is_tombstone true for live capability")
    live_result = resolve("skill.never-tombstoned", n_ids, n_by)
    if live_result.status != LIVE or live_result.terminal_id != "skill.never-tombstoned":
        return fail(
            f"live capability status={live_result.status} "
            f"terminal={live_result.terminal_id} (must not enter tombstone path)"
        )
    selected = route_selection("skill.never-tombstoned", n_ids, n_by)
    if selected != "skill.never-tombstoned":
        return fail(f"live route_selection mutated id -> {selected!r}")

    print(
        "cycle=CYCLE dead=DEAD/missing-target "
        "negative=LIVE/not-tombstone"
    )
    print("SUCCESS:IMP-0405-probe2 cycle test and live-capability negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
