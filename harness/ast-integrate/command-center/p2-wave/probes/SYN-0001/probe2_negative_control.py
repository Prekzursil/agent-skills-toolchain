#!/usr/bin/env python3
"""Probe 2: 20 unrelated findings must not collapse to one shared root cause."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    cur = HERE
    for _ in range(8):
        if (cur / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return cur
        cur = cur.parent
    raise SystemExit("FAILED:SYN-0001 repo-root-not-found")


REPO = repo_root()
sys.path.insert(0, str(HERE))

import builder as B  # noqa: E402

OUT = REPO / "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"


def fail(why: str) -> int:
    print(f"FAILED:SYN-0001-probe2 {why}")
    return 1


def main() -> int:
    unrelated = B.unrelated_fixture(20)
    families = {r["family_id"] for r in unrelated}
    if len(families) != 20:
        return fail("fixture-not-20-families")
    built = B.build_graph(unrelated)
    B.assert_build_ok(built, require_depth=False)
    print(
        f"unrelated roots={len(built['root_ids'])} edges={len(built['edges'])} "
        f"families={built['family_count']} super_root={built['shared_super_root']}"
    )
    if built["shared_super_root"]:
        return fail("builder-invented-super-root")
    if built["edges"]:
        return fail("unrelated-edges-invented")
    if len(built["root_ids"]) == 1:
        return fail("single-shared-root-cause")
    if len(built["root_ids"]) != 20:
        return fail(f"expected-20-roots got={len(built['root_ids'])}")

    related = B.build_graph(B.related_cluster_fixture())
    print(
        f"related roots={len(related['root_ids'])} "
        f"depth={related['metrics']['max_depth']}"
    )
    if len(related["root_ids"]) != 1:
        return fail("related-cluster-should-share-one-cause")
    if related["metrics"]["max_depth"] < 2:
        return fail("related-cluster-not-a-hierarchy")

    mixed = B.build_graph(unrelated + B.related_cluster_fixture())
    print(f"mixed roots={len(mixed['root_ids'])} (expect 21 = 20+1)")
    if len(mixed["root_ids"]) != 21:
        return fail(f"mixed-collapsed roots={len(mixed['root_ids'])}")

    if OUT.is_file():
        live = json.loads(OUT.read_text(encoding="utf-8"))
        causes = [
            n["id"] for n in live.get("nodes") or [] if n.get("type") == "CAUSE"
        ]
        print(f"live_cause_count={len(causes)}")
        if len(causes) < 2:
            return fail("live-artifact-is-a-single-root")
        if live.get("shared_super_root") is True:
            return fail("live-artifact-flags-super-root")

    print(
        "SUCCESS:SYN-0001-probe2 negative-control 20-unrelated-not-one-root"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
