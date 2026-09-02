#!/usr/bin/env python3
"""Probe 1: unpack the shipped artifact and set-difference against the SBOM."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0058-probe1 {msg}")
    return 1


def main() -> int:
    live = C.setdiff()
    summary = {
        "artifact_purls": live["artifact_purls"],
        "declared_in_both": live["declared_in_both"],
        "enumeration_broken": live["enumeration_broken"],
        "in_both": live["in_both"],
        "listed_in_sbom_absent_from_artifact": live["listed_in_sbom_absent_from_artifact"],
        "pass": live["pass"],
        "plants_in_artifact": live["plants_in_artifact"],
        "plants_in_sbom": live["plants_in_sbom"],
        "present_in_artifact_absent_from_sbom": live["present_in_artifact_absent_from_sbom"],
        "probe": live["probe"],
        "sbom_purls": live["sbom_purls"],
        "unit_id": live["unit_id"],
        "zero_difference": live["zero_difference"],
        "zip": live["zip"],
    }
    print(json.dumps(summary, sort_keys=True))

    if not live["pass"]:
        return fail("set-diff control failed (declared missing or enumeration broken)")
    if not live["plants_in_artifact"]:
        return fail("planted components not found in artifact enumeration")
    if live["zero_difference"]:
        return fail("zero-difference while plants should be unlisted")
    if not live["present_in_artifact_absent_from_sbom"]:
        return fail("no SBOM gaps; planted completeness claim was not refuted")

    if not C.ART.is_file() or C.ART.stat().st_size < 200:
        return fail("artifact missing")
    text = C.ART.read_text(encoding="utf-8")
    if C.CATALOG_SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0058":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    rec = doc.get("probe1_setdiff") or {}
    if rec.get("artifact_purls") != live["artifact_purls"]:
        return fail("artifact_purls drifted from live unpack")
    if rec.get("present_in_artifact_absent_from_sbom") != live["present_in_artifact_absent_from_sbom"]:
        return fail("set-diff missing-from-sbom drifted")
    if rec.get("declared_in_both") is not True:
        return fail("artifact lost declared-in-both")
    if rec.get("zero_difference") is not False:
        return fail("artifact claims zero-difference")

    print(
        f"artifact_n={len(live['artifact_purls'])} sbom_n={len(live['sbom_purls'])} "
        f"missing_from_sbom={len(live['present_in_artifact_absent_from_sbom'])} "
        f"declared_in_both={live['declared_in_both']}"
    )
    print("SUCCESS:ADV-0058-probe1 artifact-vs-sbom set-diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
