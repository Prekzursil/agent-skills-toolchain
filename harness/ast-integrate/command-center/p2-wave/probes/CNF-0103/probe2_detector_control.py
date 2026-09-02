#!/usr/bin/env python3
"""Probe 2: DETECTOR CONTROL — swallowed-zero vs honest walk vs empty tree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from measure import OUT, UNIT, live, payload_from_doc  # noqa: E402

ART = REPO / OUT


def main() -> int:
    if not ART.is_file():
        print(f"FAILED:{UNIT}-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    measured = live()
    det = measured["both_states"]
    print(
        json.dumps(
            {
                "probe": "probe2-detector-control",
                "fired_on_bad": det["fired_on_bad"],
                "silent_on_good": det["silent_on_good"],
                "bad_file_count": det["bad_file_count"],
                "good_file_count": det["good_file_count"],
                "known_fixture_count": det["known_fixture_count"],
                "empty_tree_count": det["empty_tree_count"],
                "distinguished": det["distinguished"],
            },
            sort_keys=True,
        )
    )
    if not det["fired_on_bad"]:
        print(f"FAILED:{UNIT}-probe2 swallowed-zero walker did not fire (count not zero on nonempty)")
        return 1
    if not det["silent_on_good"]:
        print(f"FAILED:{UNIT}-probe2 honest walker did not report known count")
        return 1
    if det["empty_tree_count"] != 0:
        print(f"FAILED:{UNIT}-probe2 empty tree was not zero")
        return 1
    if det["bad_file_count"] == det["empty_tree_count"] and det["known_fixture_count"] > 0:
        # Same number (0) but different cause — that IS the distinction we record.
        if not det["distinguished"]:
            print(f"FAILED:{UNIT}-probe2 failed to mark swallowed-zero as distinct from empty")
            return 1
    payload = payload_from_doc(doc)
    recorded = (payload.get("detector_controls") or [None])[0] or {}
    if not recorded.get("fired_on_bad") or not recorded.get("silent_on_good"):
        print(f"FAILED:{UNIT}-probe2 artifact detector_controls do not record both states")
        return 1
    if int(recorded.get("known_fixture_count") or 0) != int(det["known_fixture_count"]):
        print(f"FAILED:{UNIT}-probe2 known count drift")
        return 1
    if doc.get("reviewer", {}).get("verdict") != "PASS":
        print(f"FAILED:{UNIT}-probe2 reviewer verdict not PASS")
        return 1
    print(
        f"fired_on_bad={det['fired_on_bad']} silent_on_good={det['silent_on_good']} "
        f"empty={det['empty_tree_count']} swallowed={det['bad_file_count']} "
        f"honest={det['good_file_count']}"
    )
    print(f"SUCCESS:{UNIT}-probe2 detector control fires on swallowed-zero, silent on honest walk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
