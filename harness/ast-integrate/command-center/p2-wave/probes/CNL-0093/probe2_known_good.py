#!/usr/bin/env python3
"""Probe 2: known-good silence, honest-revision negative control, FP rate.

Detector-control runs first: planted-bad must still FIRE before any absence
is reported. Mechanically independent of probe 1's process: this script
reloads fixtures and recomputes detect() across four councils, then reports
the false-positive rate as a number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from detector import detect, load_council  # noqa: E402

PLANTED = HERE / "fixtures" / "planted-bad.json"
GOOD = HERE / "fixtures" / "known-good.json"
REVISION = HERE / "fixtures" / "honest-revision.json"
NON_PIVOTAL = HERE / "fixtures" / "non-pivotal.json"


def run(path: Path) -> dict:
    council = load_council(path)
    result = detect(council)
    return {"id": council["id"], "fires": bool(result["fires"]), "result": result}


def main() -> int:
    planted = run(PLANTED)
    print(f"detector_control_known_present_found={planted['fires']}")
    if not planted["fires"]:
        print("FAILED:CNL-0093-probe2 detector-control planted-bad silent")
        return 1

    good = run(GOOD)
    revision = run(REVISION)
    non_pivotal = run(NON_PIVOTAL)

    clean = [good, revision, non_pivotal]
    false_positives = sum(1 for c in clean if c["fires"])
    n_clean = len(clean)
    fp_rate = false_positives / n_clean

    print(f"silent_on_known_good={not good['fires']}")
    print(f"silent_on_honest_revision={not revision['fires']}")
    print(f"silent_on_non_pivotal={not non_pivotal['fires']}")
    print(f"false_positive_count={false_positives}")
    print(f"false_positive_denominator={n_clean}")
    print(f"false_positive_rate={fp_rate}")
    print(
        "negative_control_verbatim="
        "honest-revision (p3 updated stated_position AND ballot to B>A>C) "
        f"fires={revision['fires']} — detector must reject this state"
    )
    print(
        json.dumps(
            {
                "planted": {"id": planted["id"], "fires": planted["fires"]},
                "known_good": {"id": good["id"], "fires": good["fires"]},
                "honest_revision": {"id": revision["id"], "fires": revision["fires"]},
                "non_pivotal": {"id": non_pivotal["id"], "fires": non_pivotal["fires"]},
                "false_positive_rate": fp_rate,
            },
            sort_keys=True,
        )
    )

    if good["fires"]:
        print("FAILED:CNL-0093-probe2 known-good fired")
        return 1
    if revision["fires"]:
        print("FAILED:CNL-0093-probe2 honest-revision fired (cannot tell revision from strategy)")
        return 1
    if non_pivotal["fires"]:
        print("FAILED:CNL-0093-probe2 non-pivotal fired")
        return 1
    if fp_rate != 0.0:
        print(f"FAILED:CNL-0093-probe2 false_positive_rate={fp_rate}")
        return 1
    print("SUCCESS:CNL-0093-probe2 known-good silent fp_rate=0.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
