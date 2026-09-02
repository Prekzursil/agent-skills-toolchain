#!/usr/bin/env python3
"""Probe 2: negative controls — correct consensus survives; late/contested stay silent.

Starts from the control fixtures, not from an author summary. A genuinely
correct instant consensus must survive re-evaluation. Unanimity after
independent briefs and a disagreement round must not fire. A contested panel
must not fire. Disabling the trigger on the planted-wrong fixture must leave
the wrong outcome in place (proves the remediation branch, not some other
path, is what changes the result).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import measure  # noqa: E402


def main() -> int:
    m = measure()
    c = m["canonical"]
    corpus = m["corpus"]
    payload = {
        "probe": "probe2-negative-controls",
        "unit_id": "IMP-0318",
        "correct_instant_fired": c["correct_instant"]["fired"],
        "correct_instant_changed": c["correct_instant"]["outcome_changed"],
        "correct_instant_survived": (
            c["correct_instant"]["fired"] and not c["correct_instant"]["outcome_changed"]
        ),
        "late_legitimate_fired": c["late_legitimate"]["fired"],
        "contested_fired": c["contested"]["fired"],
        "trigger_disabled_fired": c["trigger_disabled"]["fired"],
        "trigger_disabled_would_have_fired": c["trigger_disabled"]["would_have_fired"],
        "enabled_vs_disabled_differ": c["trigger_disabled"]["outcomes_differ"],
        "correct_instant_all_survived": corpus["correct_instant_all_survived"],
        "pass": bool(
            c["correct_instant"]["ok"]
            and c["late_legitimate"]["ok"]
            and c["contested"]["ok"]
            and c["trigger_disabled"]["ok"]
            and (not c["late_legitimate"]["fired"])
            and (not c["contested"]["fired"])
            and corpus["correct_instant_all_survived"]
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0318-probe2 negative controls")
        return 1
    print(
        "correct_survived "
        f"{c['correct_instant']['first_outcome']} "
        f"late_fired={c['late_legitimate']['fired']} "
        f"contested_fired={c['contested']['fired']} "
        f"disabled_differs={c['trigger_disabled']['outcomes_differ']}"
    )
    print("SUCCESS:IMP-0318-probe2 correct survives; late/contested silent; disable holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
