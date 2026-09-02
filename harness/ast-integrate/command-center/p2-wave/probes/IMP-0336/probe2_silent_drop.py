#!/usr/bin/env python3
"""IMP-0336 probe 2: adversarial silent-drop; traceability count must FALL.

Reviewer starts from this test, not from an author summary: drop one harvested
mode from the action plan without accepting it, then recompute bind().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from reviewer import review_silent_drop  # noqa: E402
from scenario import evaluate_silent_drop  # noqa: E402


def main() -> int:
    drop = evaluate_silent_drop()
    review = review_silent_drop()
    payload = {
        "probe": "probe2-silent-drop",
        "unit_id": "IMP-0336",
        "silent_drop": drop,
        "reviewer": review,
        "pass": bool(drop["pass"] and review["pass"]),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0336-probe2 silent-drop traceability did not fall")
        return 1
    print(
        "good_count={0} bad_count={1} falls={2} reviewer={3}".format(
            drop["good_count"],
            drop["bad_count"],
            drop["count_falls"],
            review["verdict"],
        )
    )
    print("SUCCESS:IMP-0336-probe2 silent drop makes traceability count FALL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
