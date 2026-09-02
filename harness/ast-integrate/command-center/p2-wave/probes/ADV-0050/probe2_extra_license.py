#!/usr/bin/env python3
"""Probe 2: restrictions expressed outside the LICENSE file.

Searches README, NOTICE, usage docs and package metadata. A LICENSE-only
no-ML rider (mcp_agent_mail, planted MIT+rider) must be invisible here; a
README/NOTICE field-of-use must be visible. Clean canonical MIT must stay silent.
Does not read probe 1's verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / A.OUTPUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0050-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if A.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0050-probe2 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0050-probe2 self-declared {doc.get('state')}")
        return 1

    live = A.run_probe2()
    art_fp = (doc.get("fingerprints") or {}).get("probe2")
    live_fp = [r["fingerprint"] for r in live["rows"]]
    payload = {
        "probe": "probe2-extra-license-search",
        "unit_id": A.UNIT_ID,
        "pass": False,
        "control_canonical_silent": live["control_canonical_silent"],
        "license_only_rider_invisible_to_probe2": live[
            "license_only_rider_invisible_to_probe2"
        ],
        "extra_license_hits": live["extra_license_hits"],
        "extra_license_classes": live["extra_license_classes"],
        "known_case_license_invisible_to_probe2": live[
            "known_case_license_invisible_to_probe2"
        ],
        "fingerprint_match": art_fp == live_fp,
        "reviewer_id": "ADV-0050-probe2-extra-license",
        "n_rows": len(live["rows"]),
    }
    payload["pass"] = bool(
        live["pass"]
        and payload["fingerprint_match"]
        and payload["control_canonical_silent"]
        and payload["license_only_rider_invisible_to_probe2"]
        and payload["known_case_license_invisible_to_probe2"]
        and payload["extra_license_hits"] >= 2
        and "non-commercial" in payload["extra_license_classes"]
        and "ethical-use" in payload["extra_license_classes"]
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not payload["pass"]:
        print(f"FAILED:ADV-0050-probe2 live={live['pass']} fp={payload['fingerprint_match']}")
        print(f"  art_fp={art_fp}")
        print(f"  live_fp={live_fp}")
        return 1
    print(
        "SUCCESS:ADV-0050-probe2 extra-LICENSE hits on README+NOTICE; "
        "LICENSE-only riders invisible; clean MIT silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
