#!/usr/bin/env python3
"""Probe 2: planted files in the zip, then SBOM listing — not a set-diff walk."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0058-probe2 {msg}")
    return 1


def main() -> int:
    live = C.plant_check()
    summary = {
        "generator_configured_to_skip_plant_paths": live[
            "generator_configured_to_skip_plant_paths"
        ],
        "independent_of_probe1_setdiff": live["independent_of_probe1_setdiff"],
        "manifest_only_generator_would_report_success": live[
            "manifest_only_generator_would_report_success"
        ],
        "pass": live["pass"],
        "plants": live["plants"],
        "plants_listed_in_sbom": live["plants_listed_in_sbom"],
        "plants_missed_by_sbom": live["plants_missed_by_sbom"],
        "plants_present_in_artifact": live["plants_present_in_artifact"],
        "probe": live["probe"],
        "unit_id": live["unit_id"],
        "zip": live["zip"],
    }
    print(json.dumps(summary, sort_keys=True))

    if not live["plants_present_in_artifact"]:
        return fail("a planted marker is missing from the shipped zip")
    if not live["plants_missed_by_sbom"]:
        return fail("every plant is listed in the SBOM; no counterexample")
    if live["plants_listed_in_sbom"]:
        return fail(f"SBOM unexpectedly lists plants {live['plants_listed_in_sbom']}")
    if not live["generator_configured_to_skip_plant_paths"]:
        return fail("generator config walks plant paths; fixture is not the attack")
    if not live["pass"]:
        return fail("plant check did not pass")

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

    rec = doc.get("probe2_plants") or {}
    if rec.get("plants_missed_by_sbom") != live["plants_missed_by_sbom"]:
        return fail("plants_missed_by_sbom drifted")
    if rec.get("plants_present_in_artifact") is not True:
        return fail("artifact lost plants_present_in_artifact")
    rec_rows = {r.get("purl"): r for r in rec.get("plants") or [] if isinstance(r, dict)}
    for row in live["plants"]:
        got = rec_rows.get(row["purl"]) or {}
        if got.get("present_in_artifact") is not True:
            return fail(f"artifact lost plant presence {row['purl']}")
        if got.get("listed_in_sbom") is not False:
            return fail(f"artifact claims SBOM lists {row['purl']}")
        if got.get("marker_path") != row["marker_path"]:
            return fail(f"marker path drifted for {row['purl']}")

    # Independent re-derivation: counterexample from zip markers, not probe-1 prose.
    missed = ",".join(live["plants_missed_by_sbom"])
    print(
        f"plants_present={live['plants_present_in_artifact']} "
        f"missed_by_sbom={missed} "
        f"generator_skips_plants={live['generator_configured_to_skip_plant_paths']}"
    )
    print("SUCCESS:ADV-0058-probe2 planted-dependency vs SBOM listing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
