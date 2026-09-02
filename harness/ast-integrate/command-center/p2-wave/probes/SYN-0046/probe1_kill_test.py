#!/usr/bin/env python3
"""Probe 1: kill-test + detector control (known-good silent, in-memory mutant fires).

Reviewer job: re-run this probe. It fires on the planted known-broken fixture
and is silent on the known-good write-as-you-go path. Re-reading a receipt
verifies nothing.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from synthesis.durability import (  # noqa: E402
    CLASS_TOTAL_LOSS,
    DEATH_SENTENCE,
    UNKNOWN,
    inspect_artifact,
    load_synthesis_lane,
    run_kill_test,
)

UNIT = "SYN-0046"
REAL = "SYN-0001"


def main() -> int:
    lane = load_synthesis_lane(REPO)
    victim = next(u for u in lane if u["id"] == REAL)
    with tempfile.TemporaryDirectory(prefix="syn-0046-kill-") as tmp:
        root = Path(tmp)
        good = run_kill_test(root / "good", victim, hold_in_memory=False, sleep_s=8.0)
        broken = run_kill_test(root / "mem", victim, hold_in_memory=True, sleep_s=8.0)
        good_path = Path(good["output_abs"])
        inspection = inspect_artifact(good_path, victim)

        payload = {
            "probe": "probe1-kill-test",
            "unit_id": UNIT,
            "real_unit_id": REAL,
            "real_output_path": victim.get("output_path"),
            "known_good": {
                "present": good["present"],
                "honest_unknown": good["honest_unknown"],
                "death_sentence_present": good["death_sentence_present"],
                "fired": good["fired"],
                "findings": good["findings"],
                "saw_marker": good["saw_marker"],
                "bytes": good_path.stat().st_size if good_path.is_file() else 0,
            },
            "known_broken_in_memory": {
                "present": broken["present"],
                "fired": broken["fired"],
                "findings": broken["findings"],
                "saw_marker": broken["saw_marker"],
            },
            "death_sentence": DEATH_SENTENCE,
            "unknown_token": UNKNOWN,
            "inspection_honest_unknown": inspection["honest_unknown"],
        }
        good_ok = (
            good["present"]
            and good["honest_unknown"]
            and good["death_sentence_present"]
            and not good["fired"]
            and good["saw_marker"]
            and inspection["honest_unknown"]
        )
        broken_ok = (
            (not broken["present"])
            and broken["fired"]
            and CLASS_TOTAL_LOSS in broken["findings"]
            and broken["saw_marker"]
        )
        payload["known_good_silent"] = good_ok
        payload["known_broken_fires"] = broken_ok
        payload["pass"] = bool(good_ok and broken_ok)
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["pass"]:
            print("FAILED:SYN-0046-probe1 kill test / detector control")
            return 1
        print(
            "SUCCESS:SYN-0046-probe1 kill test left an honest UNKNOWN skeleton "
            "on SYN-0001; in-memory mutant fired total-loss-on-freeze"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
