#!/usr/bin/env python3
"""Probe 2: adversarial both-states — artificially short timeout must be reported."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from join import synthetic_both_states  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0243.json"
SENTINEL = "SUCCESS:TST-0243"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    control = synthetic_both_states()
    payload = {
        "probe": "probe2-short-timeout-control",
        "unit_id": "TST-0243",
        "control": control,
        "pass": control["pass"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print("FAILED:TST-0243-probe2 self-declared", st)
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0243-probe2 sentinel-absent")
            return 1
        rec = doc.get("both_states") or {}
        if rec.get("fires_on_short_timeout") is not True:
            print("FAILED:TST-0243-probe2 receipt missing short-timeout fire")
            return 1
        if rec.get("silent_on_good") is not True:
            print("FAILED:TST-0243-probe2 receipt missing silent-on-good")
            return 1

    if not control["silent_on_good"]:
        print("FAILED:TST-0243-probe2 good-state timeout was reported as a defect")
        return 1
    if not control["fires_on_short_timeout"]:
        print("FAILED:TST-0243-probe2 artificially short timeout was not reported")
        return 1
    if not control["control_class_untouched"]:
        print("FAILED:TST-0243-probe2 overlay leaked onto the untouched class")
        return 1
    if not control["proposed_present"]:
        print("FAILED:TST-0243-probe2 defect missing proposed_new_timeout")
        return 1
    broken = control["broken"]
    if broken["timeout_min"] != 1:
        print("FAILED:TST-0243-probe2 overlay did not plant timeout=1")
        return 1
    if broken["verdict"] != "DEFECT":
        print("FAILED:TST-0243-probe2 short timeout verdict", broken["verdict"])
        return 1
    print(
        f"silent_on_good={control['silent_on_good']} "
        f"fires_on_short={control['fires_on_short_timeout']} "
        f"proposed={broken['proposed_new_timeout_seconds']}"
    )
    print("SUCCESS:TST-0243-probe2 short timeout reported; adequate timeout silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
