#!/usr/bin/env python3
"""Probe 1: redirect test on a real tombstone, plus current-tree census.

Mechanically this walks on-disk SKILL.md / JSON tombstone records, then
calls route_selection. It does not construct an in-memory cycle graph
(that is probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.tombstones import (  # noqa: E402
    RESOLVED,
    DeadSelectionError,
    Root,
    default_roots,
    discover,
    index_from_records,
    route_selection,
    scan_roots,
    tombstone_table,
)

REAL_OLD = "skill.four-voice-prompt"
REAL_NEW = "skill.council"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0405-probe1 {msg}")
    return 1


def fixture_redirect_root() -> Root:
    return Root(
        "fixture-redirect",
        HERE / "fixtures" / "trees" / "redirect" / "skills",
        "skill",
    )


def main() -> int:
    census = scan_roots(repo=REPO, home=Path.home())
    table = census["tombstone_table"]
    redirect_rows = [r for r in table if r.get("new_id")]
    print(
        json.dumps(
            {
                "probe": "probe1-redirect",
                "unit_id": "IMP-0405",
                "redirect_tombstone_count": census["redirect_tombstone_count"],
                "live_count": census["live_count"],
                "roots_existing": [
                    r["name"] for r in census["roots"] if r["exists"]
                ],
                "tombstone_table": table,
            },
            sort_keys=True,
        )
    )

    real = [r for r in redirect_rows if r["old_id"] == REAL_OLD]
    if not real:
        return fail(f"real tombstone {REAL_OLD} absent from current trees")
    row = real[0]
    if row["resolution"] != RESOLVED or row["terminal_id"] != REAL_NEW:
        return fail(
            f"real tombstone did not resolve {row['old_id']} -> {REAL_NEW} "
            f"got resolution={row['resolution']} terminal={row['terminal_id']} "
            f"defect={row['defect']}"
        )
    if row.get("defect"):
        return fail(f"real tombstone recorded as defect={row['defect']}")

    live, tombs = discover(default_roots(repo=REPO), repo=REPO)
    live_ids, by_old = index_from_records(live, tombs)
    try:
        selected = route_selection(REAL_OLD, live_ids, by_old)
    except DeadSelectionError as exc:
        return fail(f"router returned dead selection: {exc}")
    if selected != REAL_NEW:
        return fail(f"route_selection({REAL_OLD})={selected!r} want {REAL_NEW}")
    if selected == REAL_OLD:
        return fail("router returned the tombstone id as the selection")

    defects = [r for r in redirect_rows if r.get("defect")]
    if defects:
        return fail(f"current-tree redirect defects {defects}")

    # Second on-disk tree: two-hop chain + JSON tombstone record.
    fr = fixture_redirect_root()
    f_live, f_tombs = discover([fr], repo=REPO)
    f_table = tombstone_table(f_live, f_tombs)
    f_ids, f_by_old = index_from_records(f_live, f_tombs)
    print(json.dumps({"fixture_redirect_table": f_table}, sort_keys=True))
    if len(f_tombs) < 3:
        return fail(f"fixture redirect tombstones={len(f_tombs)} want >=3")
    chained = route_selection("skill.old-name", f_ids, f_by_old)
    if chained != "skill.live-target":
        return fail(f"chain skill.old-name -> {chained!r} want skill.live-target")
    aliased = route_selection("skill.json-alias", f_ids, f_by_old)
    if aliased != "skill.live-target":
        return fail(f"json alias -> {aliased!r} want skill.live-target")
    mid = route_selection("skill.mid-name", f_ids, f_by_old)
    if mid != "skill.live-target":
        return fail(f"mid hop returned {mid!r}")
    for hop in ("skill.old-name", "skill.mid-name", "skill.json-alias"):
        if hop == chained or hop == aliased or hop == mid:
            return fail(f"selection was a tombstone id {hop}")

    print(
        f"real {REAL_OLD} -> {selected} "
        f"tree_redirects={census['redirect_tombstone_count']} "
        f"fixture_chain={chained} json_alias={aliased}"
    )
    print("SUCCESS:IMP-0405-probe1 redirect test on a real tombstone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
