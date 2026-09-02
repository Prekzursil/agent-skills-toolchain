#!/usr/bin/env python3
"""Probe 2: holdout tokens never appear in implementation-unit input lists.

Mechanically different from probe 1: scans WORK-UNIT-CATALOG.json inputs.
Does not score candidates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import corpus as K  # noqa: E402
import provenance as P  # noqa: E402

ART = REPO / C.OUTPUT_REL
UNIT = C.UNIT_ID


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    corpus = K.build_corpus()
    scan = P.scan_catalog(corpus)
    payload = {
        "probe": "probe2-holdout-provenance",
        "unit_id": UNIT,
        "implementation_units_scanned": scan["implementation_units_scanned"],
        "leak_count": scan["leak_count"],
        "planted_control_fired": scan["planted_control_fired"],
        "holdout_ids": scan["holdout_ids"],
        "clean": scan["clean"],
        "pass": scan["clean"] and scan["planted_control_fired"],
    }
    print(json.dumps(payload, sort_keys=True))
    if scan["implementation_units_scanned"] < 1:
        return fail("no implementation units scanned")
    if scan["leak_count"] != 0:
        return fail(f"holdout leaked into IMP inputs: {scan['leaks']}")
    if scan["non_implementation_leaks"]:
        return fail(
            "holdout tokens found in non-IMP inputs: "
            f"{scan['non_implementation_leaks']}"
        )
    if not scan["planted_control_fired"]:
        return fail("planted holdout id did not fire the scanner")
    if len(scan["holdout_ids"]) < C.MIN_SPLIT:
        return fail("holdout split undersized")
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    prov = doc.get("provenance") or {}
    if prov.get("leak_count") != 0:
        return fail("receipt leak_count drift")
    if prov.get("planted_control_fired") is not True:
        return fail("receipt planted_control_fired drift")
    rec_ids = list(prov.get("holdout_ids") or [])
    if rec_ids != scan["holdout_ids"]:
        return fail("receipt holdout_ids drift")
    print(
        f"impl_scanned={scan['implementation_units_scanned']} "
        f"leak_count=0 planted_control_fired=True"
    )
    print("SUCCESS:TST-0232-probe2 holdout absent from implementation inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
