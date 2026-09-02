#!/usr/bin/env python3
"""Probe 1: pre-registration hash match, +0.01 mutation fires, ordering."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prereg as P  # noqa: E402

REPO = HERE.parents[3]


def main() -> int:
    rubric = REPO / P.RUBRIC_REL
    manifest = REPO / P.MANIFEST_REL
    if not rubric.is_file() or not manifest.is_file():
        print("FAILED:ARC-0002-probe1 missing RUBRIC.json or ARTIFACT-MANIFEST.json")
        return 1
    match = P.check_hash_match(rubric, manifest)
    mut = P.mutation_fires(rubric, manifest)
    order = P.check_ordering(REPO, manifest)
    early = P.ordering_negative_control(REPO, manifest)
    print(json.dumps(
        {
            "probe": "probe1-preregistration",
            "unit_id": "ARC-0002",
            "hash_match": match,
            "mutation": mut,
            "ordering": order,
            "early_mtime_negative_control": early,
        },
        indent=2,
        sort_keys=True,
    ))
    print(
        f"hash_match={match.get('ok')} mutation_fired={mut.get('ok')} "
        f"order_ok={order.get('ok')} early_mtime_fails={early.get('ok')}"
    )
    if not (match.get("ok") and mut.get("ok") and order.get("ok") and early.get("ok")):
        print("FAILED:ARC-0002-probe1 pre-registration or negative control")
        return 1
    print("SUCCESS:ARC-0002-probe1 pre-registration hash, mutation fire, ordering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
