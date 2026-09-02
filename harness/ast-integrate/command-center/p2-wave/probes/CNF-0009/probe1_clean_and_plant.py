#!/usr/bin/env python3
"""Probe 1: recompute both difference directions and the same-run planted P0 control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import comparator as C  # noqa: E402

ART = REPO / C.OUTPUT_REL
SENTINEL = C.COMPLETION_SENTINEL


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0009-probe1 {msg}")
    return 1


def main() -> int:
    live = C.measure()
    clean = live["clean"]
    planted = live["planted"]
    print(
        json.dumps(
            {
                "probe": "probe1-clean-and-plant",
                "source": live["pair"]["source"],
                "registry_minus_frame": clean["registry_minus_frame_verbatim"],
                "frame_minus_registry": clean["frame_minus_registry_verbatim"],
                "planted_rmf": planted["registry_minus_frame_verbatim"],
                "planted_nonzero": planted["nonzero_difference"],
                "same_run": planted["same_run_as_clean"],
            },
            sort_keys=True,
        )
    )
    if clean["registry_minus_frame"] != []:
        return fail(f"clean registry-minus-frame={clean['registry_minus_frame']}")
    if clean["frame_minus_registry"] != []:
        return fail(f"clean frame-minus-registry={clean['frame_minus_registry']}")
    if not planted["nonzero_difference"] or not planted["contains_planted_id"]:
        return fail("planted P0 control did not produce a non-zero difference")
    if not planted["same_run_as_clean"]:
        return fail("planted control was not in the same run as clean")
    if C.PLANTED_P0 not in planted["registry_minus_frame"]:
        return fail("planted id missing from planted difference")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("completion_sentinel absent")
    doc = json.loads(text)
    ok, why = C.validate_against_schema(doc)
    if not ok:
        return fail(f"schema {why}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    domain = C.domain_from_doc(doc)
    if domain.get("registry_minus_frame") != clean["registry_minus_frame"]:
        return fail("artifact registry_minus_frame drifted from live recompute")
    if domain.get("frame_minus_registry") != clean["frame_minus_registry"]:
        return fail("artifact frame_minus_registry drifted from live recompute")
    art_plant = domain.get("planted_id_control") or {}
    if art_plant.get("registry_minus_frame") != planted["registry_minus_frame"]:
        return fail("artifact planted difference drifted from live recompute")
    if not art_plant.get("nonzero_difference"):
        return fail("artifact planted control reports zero difference")
    print("schema_ok=True plant_fires=True both_directions_empty=True")
    print("SUCCESS:CNF-0009-probe1 clean difference and same-run planted P0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
