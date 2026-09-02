#!/usr/bin/env python3
"""Probe 2: empty / small-falsification / padded through every extracted gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0089-volume-as-quality-gate-rejection.json"


def main() -> int:
    live = I.compare_outputs()
    print(json.dumps(live, sort_keys=True))
    if not live["empty_control_ok"]:
        print("FAILED:ADV-0089-probe2 empty fixture did not fail every gate")
        return 1
    mutant = live["exemption_mutant"]
    if not mutant["fired_on_bad_state"] or not mutant["silent_on_good_state"]:
        print("FAILED:ADV-0089-probe2 NC-EMPTY-SMALL-EXEMPTION both-states")
        return 1
    if live["volume_defect_count"] < 1:
        print("FAILED:ADV-0089-probe2 padded did not pass where small falsification failed")
        return 1
    if "named-probe-stat-size-200" not in live["volume_defect_ids"]:
        print("FAILED:ADV-0089-probe2 200-byte named-probe floor did not discriminate")
        return 1
    small_n = int(live["fixtures"]["small_bytes"])
    padded_n = int(live["fixtures"]["padded_bytes"])
    if small_n >= 200 or padded_n < 2048:
        print(
            f"FAILED:ADV-0089-probe2 fixture sizes small={small_n} padded={padded_n}"
        )
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0089-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0089-probe2 self-declared {doc.get('state')}")
        return 1
    if I.CATALOG_SENTINEL not in text:
        print("FAILED:ADV-0089-probe2 catalog sentinel absent")
        return 1
    recorded = doc.get("probe2_live") or {}
    if int(recorded.get("volume_defect_count") or -1) != live["volume_defect_count"]:
        print("FAILED:ADV-0089-probe2 artifact volume_defect_count drifted")
        return 1
    if list(recorded.get("volume_defect_ids") or []) != live["volume_defect_ids"]:
        print("FAILED:ADV-0089-probe2 artifact volume_defect_ids drifted")
        return 1
    ncs = doc.get("negative_controls") or []
    if not any(
        c.get("id") == "NC-EMPTY-SMALL-EXEMPTION"
        and c.get("fired_on_bad_state") is True
        and c.get("silent_on_good_state") is True
        for c in ncs
        if isinstance(c, dict)
    ):
        print("FAILED:ADV-0089-probe2 negative control missing from artifact")
        return 1
    tests = doc.get("tests") or []
    if any(t.get("result") not in {"PASS", "FAIL", "NOT-RUN"} for t in tests):
        print("FAILED:ADV-0089-probe2 tests missing results")
        return 1
    if not any(t.get("result") == "PASS" for t in tests):
        print("FAILED:ADV-0089-probe2 no passing tests recorded")
        return 1
    print("SUCCESS:ADV-0089-probe2 empty/small/padded differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
