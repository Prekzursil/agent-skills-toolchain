#!/usr/bin/env python3
"""Probe 1: rebuild the revision-by-capability matrix from frozen schemas.

Fails unless every live artifact cell cites spec_revision_id and matches the
rebuild (capability, spec_revision_id, presence).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
sys.path.insert(0, str(PROBE))
from matrix import (  # noqa: E402
    REVISIONS,
    assert_every_cell_cites_revision,
    build_matrix,
)

ARTIFACT = REPO / "command-center" / "research" / "RES-0036.json"


def main() -> int:
    rebuilt = build_matrix()
    assert_every_cell_cites_revision(rebuilt)
    if not ARTIFACT.is_file():
        print("FAILED:RES-0036-probe1 artifact missing")
        return 1
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    live = (((doc.get("matrix") or {}).get("cells")) or [])
    if not isinstance(live, list) or not live:
        print("FAILED:RES-0036-probe1 artifact has no matrix.cells")
        return 1
    live_idx = {}
    for cell in live:
        if not isinstance(cell, dict):
            print("FAILED:RES-0036-probe1 non-object cell")
            return 1
        rid = cell.get("spec_revision_id")
        cap = cell.get("capability")
        if rid not in REVISIONS:
            print(f"FAILED:RES-0036-probe1 cell lacks valid spec_revision_id: {cell}")
            return 1
        if not cap:
            print(f"FAILED:RES-0036-probe1 cell lacks capability: {cell}")
            return 1
        live_idx[(cap, rid)] = cell.get("presence")
    rebuilt_idx = {(c["capability"], c["spec_revision_id"]): c["presence"] for c in rebuilt["cells"]}
    if live_idx != rebuilt_idx:
        missing = sorted(set(rebuilt_idx) - set(live_idx))[:8]
        extra = sorted(set(live_idx) - set(rebuilt_idx))[:8]
        drift = [
            (k, live_idx[k], rebuilt_idx[k])
            for k in sorted(set(live_idx) & set(rebuilt_idx))
            if live_idx[k] != rebuilt_idx[k]
        ][:8]
        print("FAILED:RES-0036-probe1 matrix drift")
        print(" missing", missing)
        print(" extra", extra)
        print(" presence_drift", drift)
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-rebuild-matrix",
                "unit_id": "RES-0036",
                "cells": len(live),
                "revisions": list(REVISIONS),
                "capabilities": rebuilt["capability_ids"],
                "every_cell_cites_spec_revision_id": True,
                "matches_schema_rebuild": True,
            },
            indent=2,
        )
    )
    print("SUCCESS:RES-0036-probe1 revision-by-capability matrix from spec schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
