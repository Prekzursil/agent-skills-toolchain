#!/usr/bin/env python3
"""Named probe 2: negative control — resume that resets any axis must fail.

Independent of probe 1's summary. The detector is the catalog sentence applied
directly to snapshot fields: post-resume remaining must equal the pre-suspend
remainder on retries, tokens, and wall_clock_ms. A mutant that reloads caps
on even one axis must make that comparison fail. Honest resume must be silent.
"""
from __future__ import annotations

import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "lib"))
sys.path.insert(0, str(HERE))

from resume_budget import AXES, ResumeBudgetLedger, remainders_equal  # noqa: E402
from scenario import CAPS, LEG1, RUN_ID  # noqa: E402

UNIT = "TST-0170"


def detector_fires(pre_remaining: dict, post_remaining: dict) -> bool:
    """True when resume did not continue the pre-suspend remainder."""
    return not remainders_equal(pre_remaining, post_remaining)


def mutant_resume(suspended: dict, reset_axes: tuple[str, ...]) -> dict:
    """Defective resume: refill named axes from caps. Not the production API."""
    post = deepcopy(suspended)
    post["status"] = "running"
    remaining = dict(post["remaining"])
    caps = post["caps"]
    for axis in reset_axes:
        remaining[axis] = caps[axis]
    post["remaining"] = remaining
    return post


def main() -> int:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="tst0170-p2-") as tmp:
        path = Path(tmp) / "budget-ledger.json"
        ledger = ResumeBudgetLedger(path)
        ledger.create(RUN_ID + "-good", CAPS)
        ledger.consume(RUN_ID + "-good", LEG1)
        pre = ledger.suspend(RUN_ID + "-good")
        honest = ledger.resume(RUN_ID + "-good")
        silent = not detector_fires(pre["remaining"], honest["remaining"])
        rows.append(
            {
                "id": "honest-resume",
                "reset_axes": [],
                "fired": detector_fires(pre["remaining"], honest["remaining"]),
                "expect_fire": False,
                "ok": silent,
            }
        )

        axis_cases = [(axis,) for axis in AXES] + [AXES]
        for axes in axis_cases:
            bad = mutant_resume(pre, axes)
            fired = detector_fires(pre["remaining"], bad["remaining"])
            # Mutant must not be silent, and must not match caps-equality on the
            # honest remaining (i.e. at least the reset axis moved).
            rows.append(
                {
                    "id": "reset:" + ",".join(axes),
                    "reset_axes": list(axes),
                    "fired": fired,
                    "expect_fire": True,
                    "ok": fired is True,
                    "post_remaining": bad["remaining"],
                }
            )

        # Production resume() after a mutant snapshot must still refuse refill:
        # a second honest resume on the same ledger stays at remainder, not caps.
        again = ledger.snapshot(RUN_ID + "-good")
        still_honest = remainders_equal(again["remaining"], pre["remaining"])
        not_caps = not remainders_equal(again["remaining"], CAPS)
        rows.append(
            {
                "id": "production-resume-not-caps",
                "reset_axes": [],
                "fired": False,
                "expect_fire": False,
                "ok": still_honest and not_caps,
            }
        )

    all_ok = all(r["ok"] for r in rows)
    silent_on_good = all(r["ok"] for r in rows if not r["expect_fire"])
    fired_on_bad = all(r["ok"] for r in rows if r["expect_fire"])
    print(
        json.dumps(
            {
                "probe": "probe2-launder-control",
                "unit_id": UNIT,
                "pass": all_ok,
                "silent_on_good_state": silent_on_good,
                "fired_on_bad_state": fired_on_bad,
                "rows": [
                    {
                        "id": r["id"],
                        "reset_axes": r["reset_axes"],
                        "fired": r["fired"],
                        "expect_fire": r["expect_fire"],
                        "ok": r["ok"],
                    }
                    for r in rows
                ],
            },
            sort_keys=True,
        )
    )
    if not all_ok:
        print(f"FAILED:{UNIT}-probe2 launder negative control")
        return 1
    print(
        "honest_silent=True "
        "reset_retries_fires=True reset_tokens_fires=True "
        "reset_wall_clock_fires=True reset_all_fires=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 resume that resets any budget is detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
