#!/usr/bin/env python3
"""Probe 1: planted orphan test and planted ghost registry entry.

Both-states: a matching tree is clean; after plants, the reconciler fires.
Collection is the CLI collector's JSON, not an in-process grep.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from test_discovery.plants import (  # noqa: E402
    build_matching_tree,
    plant_orphan_python,
    plant_orphan_vitest,
    write_ghost_registry,
)
from test_discovery.reconcile import reconcile_tree  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0326-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0326-p1-") as raw:
        base = Path(raw)

        matching = build_matching_tree(base / "match")
        clean = reconcile_tree(
            matching["root"], matching["registry"], via_cli=True
        )
        if not clean.complete:
            return fail(f"matching walk incomplete: {clean.errors}")
        if clean.paths_walked <= 0:
            return fail("matching walk visited zero paths")
        if clean.orphans:
            return fail(f"matching tree reported orphans {clean.orphans}")
        if clean.ghosts:
            return fail(f"matching tree reported ghosts {clean.ghosts}")
        if clean.collected_count < 3:
            return fail(f"matching collected {clean.collected_count}")

        orphan_root = base / "orphan"
        planted = build_matching_tree(orphan_root)
        py_orphan = plant_orphan_python(Path(planted["root"]))
        js_orphan = plant_orphan_vitest(Path(planted["root"]))
        orp = reconcile_tree(planted["root"], planted["registry"], via_cli=True)
        orphan_hits = [n for n in orp.orphans if "planted orphan" in n or "test_planted_orphan" in n]
        if len(orphan_hits) < 2:
            return fail(f"planted orphans not both reported: {orp.orphans}")
        if "tests/test_registered.py::test_ok" not in orp.registered_and_collected:
            return fail("registered test dropped when orphan planted")

        ghost_root = base / "ghost"
        planted_g = build_matching_tree(ghost_root)
        ghost_reg = write_ghost_registry(Path(planted_g["root"]), planted_g)
        gh = reconcile_tree(planted_g["root"], ghost_reg, via_cli=True)
        if gh.orphans:
            return fail(f"ghost-only plant reported orphans {gh.orphans}")
        if not any("test_ghost_not_on_disk" in g for g in gh.ghosts):
            return fail(f"ghost entry not reported: {gh.ghosts}")

        payload = {
            "probe": "probe1-orphan-and-ghost",
            "unit_id": "TST-0326",
            "collector": clean.collector,
            "matching": {
                "orphan_count": len(clean.orphans),
                "ghost_count": len(clean.ghosts),
                "collected_count": clean.collected_count,
                "paths_walked": clean.paths_walked,
                "nodeids": clean.registered_and_collected,
            },
            "orphan_control": {
                "planted_python": str(py_orphan),
                "planted_vitest": str(js_orphan),
                "orphans": orp.orphans,
                "orphan_count": len(orp.orphans),
            },
            "ghost_control": {
                "ghosts": gh.ghosts,
                "ghost_count": len(gh.ghosts),
            },
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "matching_clean=True "
            f"orphans={orp.orphans} ghosts={gh.ghosts} "
            f"paths_walked={clean.paths_walked}"
        )
        print(
            "SUCCESS:TST-0326-probe1 planted orphan and ghost detected; "
            "matching tree empty diffs"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
