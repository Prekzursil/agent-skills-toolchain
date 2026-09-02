#!/usr/bin/env python3
"""Probe 2: independent reviewer re-runs the detector control on the known-broken fixture.

Derives the planted-P0 and missing-P0 verdicts BEFORE reading the artifact
conclusion. A reviewer who only re-reads the result has verified nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import comparator as C  # noqa: E402

ART = REPO / C.OUTPUT_REL
MISSING_P0 = "CLM-P0-BETA"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0009-probe2 {msg}")
    return 1


def main() -> int:
    pair = C.load_measured_pair()
    clean = C.compare_docs(pair["registry_doc"], pair["frame_doc"])
    planted = C.plant_p0(clean)
    broken_frame = C.drop_frame_id(pair["frame_doc"], MISSING_P0)
    broken = C.compare_docs(pair["registry_doc"], broken_frame)
    derived = {
        "probe": "probe2-reviewer-detector",
        "planted_fires": bool(planted["nonzero_difference"] and planted["contains_planted_id"]),
        "planted_rmf": planted["registry_minus_frame_verbatim"],
        "missing_p0": MISSING_P0,
        "broken_rmf": broken["registry_minus_frame_verbatim"],
        "broken_fires": MISSING_P0 in broken["registry_minus_frame"],
        "clean_rmf_empty": clean["registry_minus_frame"] == [],
        "clean_fmr_empty": clean["frame_minus_registry"] == [],
    }
    print(json.dumps(derived, sort_keys=True))
    if not derived["planted_fires"]:
        return fail("planted P0 control silent")
    if not derived["broken_fires"]:
        return fail("missing-P0 fixture did not make registry-minus-frame non-empty")
    if derived["broken_rmf"] == clean["registry_minus_frame_verbatim"]:
        return fail("missing-P0 fixture indistinguishable from clean (inert detector)")
    if not derived["clean_rmf_empty"] or not derived["clean_fmr_empty"]:
        return fail("clean pair is not empty in both directions")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0009":
        return fail(f"unit_id {doc.get('unit_id')}")
    domain = C.domain_from_doc(doc)
    art_plant = domain.get("planted_id_control") or {}
    if not art_plant.get("nonzero_difference") or not art_plant.get("contains_planted_id"):
        return fail("artifact did not record detector-control fire")
    if art_plant.get("planted_id") != C.PLANTED_P0:
        return fail("artifact planted_id mismatch")
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("reviewer not independent")
    print("independent_ok=True planted_fires=True missing_p0_fires=True")
    print("SUCCESS:CNF-0009-probe2 reviewer detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
