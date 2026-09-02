#!/usr/bin/env python3
"""Named probe 1: live pattern census plus planted-fixture control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from helpers import OUT_REL, REPO, SENTINEL, UNIT  # noqa: E402
from scan_hazards import scan_controls, scan_tree  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:AUD-0086-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        print("FAILED:AUD-0086-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0086-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0086-probe1 self-declared", doc.get("state"))
        return 1

    live = scan_tree()
    recorded = list((doc.get("pattern_scan") or {}).get("fingerprints") or [])
    if live["fingerprints"] != recorded:
        print("FAILED:AUD-0086-probe1 fingerprint mismatch")
        print(
            json.dumps(
                {"live_n": live["hit_count"], "recorded_n": len(recorded)},
                sort_keys=True,
            )
        )
        return 1

    ctrl = scan_controls()
    if not ctrl.get("fired_on_bad") or not ctrl.get("silent_on_good"):
        print("FAILED:AUD-0086-probe1 planted fixtures did not discriminate")
        print(
            json.dumps(
                {
                    "fired_on_bad": ctrl.get("fired_on_bad"),
                    "silent_on_good": ctrl.get("silent_on_good"),
                    "missing_on_bad": ctrl.get("missing_on_bad"),
                    "good_hits": ctrl.get("good_hits"),
                },
                sort_keys=True,
            )
        )
        return 1

    summary = {
        "probe": "probe1-pattern-census",
        "unit_id": UNIT,
        "pass": True,
        "files_scanned": live["files_scanned"],
        "hit_count": live["hit_count"],
        "rule_counts": live["rule_counts"],
        "control_fired_on_bad": True,
        "control_silent_on_good": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:AUD-0086-probe1 pattern-census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
