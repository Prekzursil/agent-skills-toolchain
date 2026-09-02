#!/usr/bin/env python3
"""Named probe 1: re-run the live filesystem sweep and check the artifact.

Recomputes the live member list from disk (not from the catalog), re-smokes
each entry in a clean temp dir, and checks that the confirmation artifact
recorded measured_executable_count before catalog_claim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sweep as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0077-blueprint-executability.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0077-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNF-0077-probe1 unparseable:{type(exc).__name__}")
        return 1
    if doc.get("unit_id") != "CNF-0077":
        print("FAILED:CNF-0077-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0077-probe1 self-declared", doc.get("state"))
        return 1
    sentinel = str(doc.get("completion_sentinel") or "")
    if "SUCCESS:CNF-0077" not in sentinel or sentinel not in text:
        print("FAILED:CNF-0077-probe1 sentinel absent")
        return 1
    if doc.get("enumeration_source") != "filesystem":
        print("FAILED:CNF-0077-probe1 enumeration_source", doc.get("enumeration_source"))
        return 1

    meas_at = text.find('"measured_executable_count"')
    claim_at = text.find('"catalog_claim"')
    if meas_at < 0 or claim_at < 0 or meas_at > claim_at:
        print("FAILED:CNF-0077-probe1 measured count is not reported first")
        return 1

    live = S.sweep_live(REPO)
    if live["measured_executable_count"] != doc.get("measured_executable_count"):
        print(
            "FAILED:CNF-0077-probe1 measured mismatch "
            f"recomputed={live['measured_executable_count']} "
            f"artifact={doc.get('measured_executable_count')}"
        )
        return 1
    if live["pre_claim_fingerprint"] != doc.get("pre_claim_fingerprint"):
        print("FAILED:CNF-0077-probe1 pre_claim_fingerprint mismatch")
        return 1
    if live["member_paths"] != list(doc.get("live_member_paths") or []):
        print("FAILED:CNF-0077-probe1 live member path mismatch")
        print("recomputed", live["member_paths"])
        print("artifact", doc.get("live_member_paths"))
        return 1
    if not S.every_row_complete(live["blueprints"]):
        print("FAILED:CNF-0077-probe1 live row missing exit_code or artifact/error")
        return 1
    if not S.every_row_complete(list(doc.get("blueprints") or [])):
        print("FAILED:CNF-0077-probe1 artifact row missing exit_code or artifact/error")
        return 1

    # Catalog must not have been the member list: artifact roots are the live FS roots.
    roots = [r.get("path") for r in (doc.get("scanned_roots") or [])]
    if "platform/workflows" not in roots or "09-WORKFLOW-BLUEPRINT-LIBRARY.json" not in roots:
        print("FAILED:CNF-0077-probe1 scanned_roots incomplete", roots)
        return 1

    claim = S.read_catalog_claim(REPO)
    if doc.get("catalog_claim") != claim["catalog_claim"]:
        print("FAILED:CNF-0077-probe1 catalog_claim mismatch")
        return 1
    if doc.get("declared_floor") != claim["declared_floor"]:
        print("FAILED:CNF-0077-probe1 declared_floor mismatch")
        return 1
    meets = live["measured_executable_count"] >= claim["declared_floor"]
    if bool(doc.get("meets_floor")) != meets:
        print("FAILED:CNF-0077-probe1 meets_floor mismatch")
        return 1

    payload = {
        "probe": "probe1-filesystem-sweep",
        "unit_id": "CNF-0077",
        "measured_executable_count": live["measured_executable_count"],
        "catalog_claim": claim["catalog_claim"],
        "declared_floor": claim["declared_floor"],
        "meets_floor": meets,
        "live_rows": len(live["blueprints"]),
        "measured_reported_first": True,
        "enumerated_from": "filesystem",
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"measured={live['measured_executable_count']} "
        f"claim={claim['catalog_claim']} floor={claim['declared_floor']} "
        f"meets={meets} rows={len(live['blueprints'])}"
    )
    print("SUCCESS:CNF-0077-probe1 filesystem sweep and measured-count-first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
