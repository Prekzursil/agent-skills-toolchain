#!/usr/bin/env python3
"""Probe 2: independent adversarial filesystem audit.

Reviewer-authored detector: plant a machine-wide cache entry outside the
clean-room profile and require the audit to name it; require silence when
the plant is not scanned; require a shared-global-cache mutant to inherit.
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
    if not ART.is_file():
        print("FAILED:TST-0177-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0177" not in json.dumps(doc):
        print("FAILED:TST-0177-probe2 sentinel absent")
        return 1
    src = str(doc.get("source_probe") or "")
    ver = str(doc.get("verifier_probe") or "")
    if not src or not ver or src == ver:
        print("FAILED:TST-0177-probe2 source/verifier missing or identical")
        return 1
    fp = H.fingerprints()
    if fp["source"] == fp["verifier"]:
        print("FAILED:TST-0177-probe2 probe file fingerprints identical")
        return 1
    if fp["source"] not in src or fp["verifier"] not in ver:
        print("FAILED:TST-0177-probe2 fingerprint not bound to record")
        print(src)
        print(ver)
        return 1

    live = H.run_scenario()
    if not live["audit"]["plant_detected"]:
        print("FAILED:TST-0177-probe2 plant not detected outside profile")
        print(json.dumps(live["audit"]["plant_hits"], sort_keys=True)[:2000])
        return 1
    if not live["audit"]["plant_outside_profile"]:
        print("FAILED:TST-0177-probe2 plant hits missing outside-profile rows")
        return 1
    for hit in live["audit"]["plant_hits"]:
        if not hit.get("has_plant_marker"):
            print("FAILED:TST-0177-probe2 plant hit missing marker", hit)
            return 1
        if not hit.get("outside_profile"):
            print("FAILED:TST-0177-probe2 plant classified as inside profile", hit)
            return 1
    if not live["audit"]["absent_silent"]:
        print("FAILED:TST-0177-probe2 detector not silent without plant")
        print(live["audit"]["absent_marker_hits"])
        return 1
    if not live["leaky_mutant"]["detected"]:
        print("FAILED:TST-0177-probe2 leaky mutant not detected")
        return 1
    if live["leaky_mutant"]["fetch_count"] != 0:
        print(
            "FAILED:TST-0177-probe2 leaky mutant still fetched; inheritance not demonstrated",
            live["leaky_mutant"],
        )
        return 1
    if not live["leaky_mutant"]["inherited_hits"]:
        print("FAILED:TST-0177-probe2 leaky mutant had no inherited hits")
        return 1
    if not live["controls"]["writes_only_inside_profile"]:
        print("FAILED:TST-0177-probe2 instrument leaked writes on the good state")
        print(live["audit"]["instrument_leaks"])
        return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:TST-0177-probe2 reviewer verdict", reviewer.get("verdict"))
        return 1
    if not reviewer.get("independent"):
        print("FAILED:TST-0177-probe2 reviewer not independent")
        return 1
    art_plant = bool((doc.get("filesystem_audit") or {}).get("plant_detected"))
    if art_plant != live["audit"]["plant_detected"]:
        print("FAILED:TST-0177-probe2 plant_detected artifact/live mismatch")
        return 1
    art_leaky = bool((doc.get("leaky_mutant") or {}).get("detected"))
    if art_leaky != live["leaky_mutant"]["detected"]:
        print("FAILED:TST-0177-probe2 leaky.detected artifact/live mismatch")
        return 1

    summary = {
        "probe": "probe2-detector-audit",
        "unit_id": "TST-0177",
        "plant_detected": True,
        "plant_outside_n": len(live["audit"]["plant_outside_profile"]),
        "absent_silent": True,
        "leaky_inherited": len(live["leaky_mutant"]["inherited_hits"]),
        "leaky_fetches": live["leaky_mutant"]["fetch_count"],
        "instrument_leaks": len(live["audit"]["instrument_leaks"]),
        "source_fp": fp["source"][:16],
        "verifier_fp": fp["verifier"][:16],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:TST-0177-probe2 machine-wide plant seen; leaky mutant inherits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
