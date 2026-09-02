#!/usr/bin/env python3
"""Probe 1: known-present hit, renamed-duplicate silent, independent work-unit recount."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import count as C  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0015.json"
KNOWN = "bp.catalog-class.discovery-only"
RENAMED = "bp.catalog-class.discovery-only-renamed"
ABSENT = "BLD-0015-SENTINEL-ABSENT-NOWHERE"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0015-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if doc.get("unit_id") != "BLD-0015":
        print("FAILED:BLD-0015-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:BLD-0015" not in blob:
        print("FAILED:BLD-0015-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:BLD-0015-probe1 self-declared", doc.get("state"))
        return 1

    dest = C.write_fixtures()
    fx = C.measure_pair(dest / "library.json", dest / "library.md")
    bp = fx["blueprints"]
    known_json = KNOWN in bp["json_ids"]
    known_md = KNOWN in bp["md_ids"]
    renamed_listed = RENAMED in bp["json_ids"] and RENAMED in bp["md_ids"]
    silent = (
        bp["raw_json_n"] == bp["measured_json"] + 1
        and bp["raw_md_n"] == bp["measured_md"] + 1
    )
    sets_ok = bp["sets_identical"]
    libj = (dest / "library.json").read_text(encoding="utf-8")
    libm = (dest / "library.md").read_text(encoding="utf-8")
    absent_ok = ABSENT not in libj and ABSENT not in libm

    live = C.live_census()
    wu_row = next(r for r in doc["floors"] if r["id"] == "work-units")
    wu_match = (
        wu_row["measured_json"] == len(live["work_unit_ids_json"])
        and wu_row["measured_md_or_text"] == len(live["work_unit_ids_text"])
        and live["work_unit_sets_identical"]
        and set(wu_row["unique_ids_or_fingerprints"]) == set(live["work_unit_ids_json"])
    )
    bp_row = next(r for r in doc["floors"] if r["id"] == "blueprints")
    fx_match = bp_row["fixture_control"]["measured_json"] == bp["measured_json"]

    ok = all(
        [
            known_json,
            known_md,
            renamed_listed,
            silent,
            sets_ok,
            absent_ok,
            wu_match,
            fx_match,
        ]
    )
    result = {
        "probe": "probe1-anti-padding",
        "unit_id": "BLD-0015",
        "known_present_json": known_json,
        "known_present_md": known_md,
        "renamed_listed": renamed_listed,
        "raw_n": bp["raw_json_n"],
        "unique_n": bp["measured_json"],
        "anti_padding_silent": silent,
        "sets_identical": sets_ok,
        "known_absent_zero": absent_ok,
        "work_unit_independent_match": wu_match,
        "work_unit_n": len(live["work_unit_ids_json"]),
        "fixture_blueprint_n": bp["measured_json"],
        "pass": ok,
    }
    print(json.dumps(result, sort_keys=True))
    print(
        f"known={known_json and known_md} renamed_listed={renamed_listed} "
        f"unique={bp['measured_json']} raw={bp['raw_json_n']} "
        f"wu={len(live['work_unit_ids_json'])} match={wu_match}"
    )
    if not ok:
        print("FAILED:BLD-0015-probe1 anti-padding or independent recount")
        return 1
    print("SUCCESS:BLD-0015-probe1 known-present, anti-padding, independent work-unit recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
