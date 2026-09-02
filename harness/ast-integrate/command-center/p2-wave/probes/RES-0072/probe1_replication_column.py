#!/usr/bin/env python3
"""Probe 1: per-router replication-status column, re-derived from fixtures.

Live check: artifact sentinel + column matches contract-graded fixtures.
Negative control: rewriting every status to replicated must go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    OUTPUT_REL,
    SENTINEL,
    UNIT_ID,
    column_from_routers,
    mutant_all_replicated,
    validate_artifact,
)

ART = REPO / OUTPUT_REL
FX = HERE / "fixtures" / "routers.json"


def main() -> int:
    fx = json.loads(FX.read_text(encoding="utf-8"))
    expected = column_from_routers(list(fx["routers"]))
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0072-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:RES-0072-probe1 catalog sentinel absent from file bytes")
        return 1
    errs = validate_artifact(doc, expected_column=expected)
    if errs:
        print("FAILED:RES-0072-probe1 " + "; ".join(errs))
        return 1
    statuses = [r["replication_status"] for r in expected]
    if "self-reported-only" not in statuses:
        print("FAILED:RES-0072-probe1 control: no self-reported-only in truth table")
        return 1
    if "replicated" in statuses:
        print("FAILED:RES-0072-probe1 unexpected replicated headline; fixtures overclaim")
        return 1
    bad = mutant_all_replicated(doc)
    bad_errs = validate_artifact(bad)
    if not bad_errs:
        print("FAILED:RES-0072-probe1 all-replicated mutant was silent")
        return 1
    payload = {
        "probe": "probe1-replication-column",
        "unit_id": UNIT_ID,
        "n_routers": len(expected),
        "statuses": statuses,
        "self_reported_only": statuses.count("self-reported-only"),
        "unknown": statuses.count("unknown"),
        "replicated": statuses.count("replicated"),
        "benchmarks": [r["benchmark"] for r in expected],
        "mutant_all_replicated_errors": bad_errs[:8],
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:RES-0072-probe1 replication-status column re-derived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
