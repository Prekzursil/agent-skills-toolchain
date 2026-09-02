#!/usr/bin/env python3
"""Claim-time duplicate check: same mechanism under a different id is caught.

Usage (from repo root):
  PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0412/claim_check.py IMP-0412
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fingerprint import collide_pair, fingerprint_parts, index_parts  # noqa: E402
from scan import load_catalog  # noqa: E402


def check_claim(
    candidate: Mapping[str, Any], catalog_units: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Return collisions between candidate and every other catalog unit."""
    cand = fingerprint_parts(candidate)
    hits: list[dict[str, Any]] = []
    for other in index_parts(catalog_units):
        if other.unit_id == cand.unit_id:
            continue
        row = collide_pair(cand, other)
        if row is not None:
            hits.append(row)
    hits.sort(key=lambda r: (r["unit_id_a"], r["unit_id_b"]))
    return hits


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("FAILED:claim_check usage claim_check.py <UNIT-ID>")
        return 2
    uid = argv[1]
    catalog = load_catalog()
    units = catalog.get("work_units") or []
    unit = next((u for u in units if u.get("id") == uid), None)
    if unit is None:
        print(f"FAILED:claim_check unknown {uid}")
        return 1
    hits = check_claim(unit, units)
    print(json.dumps({"unit_id": uid, "collisions": hits, "count": len(hits)}, sort_keys=True))
    if hits:
        print(f"CLAIM-COLLISION {uid} n={len(hits)}")
    else:
        print(f"CLAIM-CLEAN {uid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
