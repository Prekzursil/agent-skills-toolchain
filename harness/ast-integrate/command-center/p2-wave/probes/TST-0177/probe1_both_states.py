#!/usr/bin/env python3
"""Probe 1: both-states — original profile still has its cache after a clean-room install.

Mechanically the source probe: re-runs the live two-profile scenario and checks
the catalog both-states control plus zero inheritance on the instrument.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 1024:
        print("FAILED:TST-0177-probe1 artifact missing or tiny")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "TST-0177":
        print("FAILED:TST-0177-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:TST-0177" not in text:
        print("FAILED:TST-0177-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0177-probe1 self-declared {st}")
        return 1
    if not doc.get("source_probe") or not doc.get("verifier_probe"):
        print("FAILED:TST-0177-probe1 empty source/verifier probe")
        return 1
    if doc["source_probe"] == doc["verifier_probe"]:
        print("FAILED:TST-0177-probe1 same-probe-rerun")
        return 1

    live = H.run_scenario()
    if not live["controls"]["both_states_original_intact"]:
        print("FAILED:TST-0177-probe1 original profile cache not intact")
        print(json.dumps(live["original"], sort_keys=True)[:2000])
        return 1
    if live["original"]["entry_count"] != len(H.PACKAGES):
        print(
            "FAILED:TST-0177-probe1 original entry_count",
            live["original"]["entry_count"],
        )
        return 1
    if not live["controls"]["zero_inherited_cleanroom"]:
        print("FAILED:TST-0177-probe1 clean-room inherited hits", live["cleanroom"]["inherited_hits"])
        return 1
    if not live["controls"]["instrument_full_fetches"]:
        print("FAILED:TST-0177-probe1 clean-room did not full-fetch")
        return 1
    if not live["cleanroom"]["empty_at_start"]:
        print("FAILED:TST-0177-probe1 clean-room not empty at start")
        return 1

    art_intact = bool((doc.get("original_profile") or {}).get("intact"))
    if art_intact != live["original"]["intact"]:
        print("FAILED:TST-0177-probe1 original.intact artifact/live mismatch")
        return 1
    art_hits = (doc.get("cleanroom_profile") or {}).get("hit_count")
    if art_hits != live["cleanroom"]["hit_count"]:
        print(
            f"FAILED:TST-0177-probe1 hit_count artifact={art_hits} live={live['cleanroom']['hit_count']}"
        )
        return 1
    if live["production"]["present"] and doc.get("verdict") == "REFUTED" and live["production_property_pass"]:
        print("FAILED:TST-0177-probe1 production property passed but artifact REFUTED")
        return 1
    if (not live["production"]["present"]) and doc.get("verdict") != "REFUTED":
        print("FAILED:TST-0177-probe1 absent production must REFUTE not", doc.get("verdict"))
        return 1
    if not live["detector_live"]:
        print("FAILED:TST-0177-probe1 detector_live false")
        return 1

    summary = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0177",
        "original_intact": live["original"]["intact"],
        "original_entries": live["original"]["entry_count"],
        "cleanroom_empty_at_start": live["cleanroom"]["empty_at_start"],
        "cleanroom_hits": live["cleanroom"]["hit_count"],
        "cleanroom_fetches": live["cleanroom"]["fetch_count"],
        "production_present": live["production"]["present"],
        "verdict": doc.get("verdict"),
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:TST-0177-probe1 original cache intact; clean-room zero inherited hits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
