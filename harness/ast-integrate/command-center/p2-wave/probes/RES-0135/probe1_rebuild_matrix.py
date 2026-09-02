#!/usr/bin/env python3
"""Probe 1: rebuild the aggregation matrix from clause-cited rules.

Independent of probe 2 (which only reads verdict counts / mutants).
Requires every cell to cite >=2 catalogued clauses whose needles are present
in the frozen snapshot bytes, and the live artifact to match the rebuild.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from matrix import (  # noqa: E402
    AXES,
    CLAUSES,
    SNAP,
    assert_every_cell_cites_clause,
    build_cells,
    load_capture,
    sha256_bytes,
    snapshot_bytes,
    snapshot_text,
    verify_clause_needles,
)

ARTIFACT = (
    REPO
    / "command-center"
    / "research"
    / "supply-chain"
    / "RES-0135-licence-compatibility-matrix-for-aggregation.json"
)


def _fail(msg: str) -> int:
    print(f"FAILED:RES-0135-probe1 {msg}")
    return 1


def main() -> int:
    missing = verify_clause_needles()
    if missing:
        return _fail("clause needles: " + "; ".join(missing[:8]))

    rebuilt = build_cells()
    assert_every_cell_cites_clause(rebuilt)

    cap = load_capture()
    rails = {r["id"]: r for r in cap.get("rails") or [] if isinstance(r, dict)}
    for spec in CLAUSES.values():
        name = spec["snapshot"]
        if name not in rails:
            return _fail(f"CAPTURE missing {name}")
        live = sha256_bytes(snapshot_bytes(name))
        if live != rails[name].get("sha256"):
            return _fail(f"CAPTURE sha mismatch {name}")
        if int(rails[name].get("http_status") or 0) != 200:
            return _fail(f"CAPTURE status {name}")

    if not ARTIFACT.is_file():
        return _fail("artifact missing")
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    live = doc.get("cells") or []
    if not isinstance(live, list) or len(live) != len(AXES) * len(AXES):
        return _fail(f"artifact cell count {len(live) if isinstance(live, list) else type(live)}")

    def key(cell: dict) -> tuple:
        return (
            cell.get("left"),
            cell.get("right"),
            cell.get("verdict"),
            cell.get("clause_number"),
            tuple(cell.get("clause_ids") or []),
            cell.get("reason_code"),
        )

    live_set = [key(c) for c in live if isinstance(c, dict)]
    rebuilt_set = [key(c) for c in rebuilt]
    if live_set != rebuilt_set:
        return _fail("artifact drift vs clause rebuild")

    unlicensed_ok = all(
        c["verdict"] == "FORBIDDEN" and "ALL-RIGHTS-RESERVED" in (c.get("notes") or "")
        for c in rebuilt
        if c["left"] == "unlicensed" or c["right"] == "unlicensed"
    )
    if not unlicensed_ok:
        return _fail("unlicensed not ALL-RIGHTS-RESERVED / FORBIDDEN")

    permissive_together = all(
        c["verdict"] == "TOGETHER"
        for c in rebuilt
        if c["left"] in {"MIT", "Apache-2.0", "BSD", "CC0", "CC-BY"}
        and c["right"] in {"MIT", "Apache-2.0", "BSD", "CC0", "CC-BY"}
    )
    if not permissive_together:
        return _fail("permissive cluster is not TOGETHER")

    # Spot-check that driving needles are not merely catalogued but in-file.
    gpl = snapshot_text("gpl-3.0.txt")
    if "You must license the entire work, as a whole, under this" not in gpl:
        return _fail("GPL §5(c) vanished from snapshot")

    print(
        json.dumps(
            {
                "probe": "probe1-rebuild-matrix",
                "unit_id": "RES-0135",
                "cells": len(rebuilt),
                "axes": list(AXES),
                "every_cell_cites_two_clauses": True,
                "needles_present": True,
                "capture_sha_matched": True,
                "matches_rebuild": True,
                "unlicensed_all_rights_reserved": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0135-probe1 clause-cited matrix rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
