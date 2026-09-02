#!/usr/bin/env python3
"""Named probe 1: re-run the live filesystem IR-load+smoke sweep.

Recomputes the live member list from disk (not from the catalog), re-attempts
IR load and smoke for each entry in a clean temp dir, and checks that the
CoverageMatrix recorded measured_executable_count before catalog_claim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402
import remaining_work as RW  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0124-blueprint-executability-gap.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0124-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:WFA-0124-probe1 unparseable:{type(exc).__name__}")
        return 1
    if doc.get("unit_id") != "WFA-0124":
        print("FAILED:WFA-0124-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("record_type") != "CoverageMatrix":
        print("FAILED:WFA-0124-probe1 record_type", doc.get("record_type"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0124-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:WFA-0124" not in text:
        print("FAILED:WFA-0124-probe1 sentinel absent")
        return 1
    if doc.get("enumeration_source") != "filesystem":
        print("FAILED:WFA-0124-probe1 enumeration_source", doc.get("enumeration_source"))
        return 1

    meas_at = text.find('"measured_executable_count"')
    claim_at = text.find('"catalog_claim"')
    if meas_at < 0 or claim_at < 0 or meas_at > claim_at:
        print("FAILED:WFA-0124-probe1 measured count is not reported first")
        return 1

    live = M.sweep_live(REPO)
    if live["measured_executable_count"] != doc.get("measured_executable_count"):
        print(
            "FAILED:WFA-0124-probe1 measured mismatch "
            f"recomputed={live['measured_executable_count']} "
            f"artifact={doc.get('measured_executable_count')}"
        )
        return 1
    if live["pre_claim_fingerprint"] != doc.get("pre_claim_fingerprint"):
        print("FAILED:WFA-0124-probe1 pre_claim_fingerprint mismatch")
        return 1
    if live["member_paths"] != list(doc.get("live_member_paths") or []):
        print("FAILED:WFA-0124-probe1 live member path mismatch")
        print("recomputed", live["member_paths"])
        print("artifact", doc.get("live_member_paths"))
        return 1
    if not M.every_row_complete(live["rows"]):
        print("FAILED:WFA-0124-probe1 live row missing IR/smoke/remaining_work")
        return 1
    if not M.every_row_complete(list(doc.get("rows") or [])):
        print("FAILED:WFA-0124-probe1 artifact row missing IR/smoke/remaining_work")
        return 1

    roots = [r.get("path") for r in (doc.get("scanned_roots") or [])]
    if "platform/workflows" not in roots or "09-WORKFLOW-BLUEPRINT-LIBRARY.json" not in roots:
        print("FAILED:WFA-0124-probe1 scanned_roots incomplete", roots)
        return 1

    claim = M.read_catalog_claim(REPO)
    if doc.get("catalog_claim") != claim["catalog_claim"]:
        print("FAILED:WFA-0124-probe1 catalog_claim mismatch")
        return 1
    if doc.get("declared_executable_floor") != claim["declared_executable_floor"]:
        print("FAILED:WFA-0124-probe1 floor mismatch")
        return 1
    meets = live["measured_executable_count"] >= claim["declared_executable_floor"]
    if bool(doc.get("meets_executable_floor")) != meets:
        print("FAILED:WFA-0124-probe1 meets_executable_floor mismatch")
        return 1

    # Do not invent catalog-sized ids when the library file is absent.
    if not live["member_paths"] and len(doc.get("rows") or []) == claim["catalog_claim"]:
        print("FAILED:WFA-0124-probe1 invented catalog-sized member list")
        return 1

    flag_ids = list(doc.get("flagship_identified") or [])
    if flag_ids != list(live["flagship_identified"]):
        print("FAILED:WFA-0124-probe1 flagship_identified mismatch", flag_ids, live["flagship_identified"])
        return 1
    expected_deficit = max(0, int(claim["flagship_required"]) - len(flag_ids))
    if doc.get("flagship_deficit") != expected_deficit:
        print("FAILED:WFA-0124-probe1 flagship_deficit mismatch")
        return 1

    backlog = list(doc.get("remaining_work_backlog") or [])
    ok_b, bad_b = RW.all_concrete(backlog)
    if not ok_b:
        print("FAILED:WFA-0124-probe1 remaining_work_backlog not concrete", bad_b)
        return 1
    tmpl = list(doc.get("member_work_template") or [])
    ok_t, bad_t = RW.all_concrete(tmpl)
    if not ok_t:
        print("FAILED:WFA-0124-probe1 member_work_template not concrete", bad_t)
        return 1

    payload = {
        "probe": "probe1-live-gap",
        "unit_id": "WFA-0124",
        "measured_executable_count": live["measured_executable_count"],
        "catalog_claim": claim["catalog_claim"],
        "declared_executable_floor": claim["declared_executable_floor"],
        "meets_executable_floor": meets,
        "live_rows": len(live["rows"]),
        "flagship_identified": live["flagship_identified"],
        "flagship_deficit": expected_deficit,
        "measured_reported_first": True,
        "enumerated_from": "filesystem",
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"measured={live['measured_executable_count']} "
        f"claim={claim['catalog_claim']} floor={claim['declared_executable_floor']} "
        f"meets={meets} rows={len(live['rows'])} flagship={len(flag_ids)}"
    )
    print("SUCCESS:WFA-0124-probe1 live IR-load+smoke gap and measured-count-first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
