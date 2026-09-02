"""Probe 2: candidate delta vs measured band; no-op is not an improvement.

Catalog tests_required:
  * measurement: candidate delta vs measured band
  * negative control: a no-op candidate must NOT be reported as an improvement

Also distinguishes measured-band gating from a vs-zero gate: a tiny
positive delta that would pass ``abs(delta) > 0`` stays inside the
measured band and must be NOT-IMPROVEMENT.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from selfimprove.measure import (  # noqa: E402
    COMPARED_AGAINST,
    Harness,
    measure_candidate,
    measure_null_change,
    measurement_session,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0372-probe2 {msg}")
    return 1


def main() -> int:
    with measurement_session() as (origin, parent):
        harness = Harness()
        null = measure_null_change(origin, harness=harness, parent=parent, label="p2-null")
        band = null["noise_band"]
        noop = measure_candidate(
            origin,
            candidate_id="noop",
            files={},
            harness=harness,
            band=band,
            parent=parent,
        )
        tiny = measure_candidate(
            origin,
            candidate_id="tiny-inside-band",
            files={"score.base": "100.10\n"},
            harness=harness,
            band=band,
            parent=parent,
        )
        real = measure_candidate(
            origin,
            candidate_id="real-gain",
            files={"score.base": "120\n"},
            harness=harness,
            band=band,
            parent=parent,
        )
        broken = measure_candidate(
            origin,
            candidate_id="regress-break",
            files={"score.base": "not-a-number\n"},
            harness=harness,
            band=band,
            parent=parent,
        )

    checks = {
        "band_measured": band["source"] == "measured-null-change" and band["assumed"] is False,
        "noop_not_improvement": noop["verdict"] == "NOT-IMPROVEMENT",
        "noop_inside_band": noop["reason"] == "inside-measured-band",
        "noop_vs_band_not_zero": noop["compared_against"] == COMPARED_AGAINST,
        "tiny_would_pass_vs_zero": tiny["would_pass_vs_zero"] is True,
        "tiny_not_improvement": tiny["verdict"] == "NOT-IMPROVEMENT",
        "tiny_inside_band": tiny["outside_band"] is False,
        "real_improvement": real["verdict"] == "IMPROVEMENT",
        "real_outside_band": real["outside_band"] is True,
        "real_not_vs_zero": real["compared_against_zero"] is False,
        "real_origin_untouched": real["isolation"]["origin_unchanged"] is True,
        "real_worktree_diverged": real["isolation"]["worktree_diverged_from_origin"] is True,
        "broken_not_improvement": broken["verdict"] == "NOT-IMPROVEMENT",
        "broken_reason_regression": broken["reason"] == "regression-failed",
        "all_compared_against_band": all(
            row["compared_against"] == COMPARED_AGAINST for row in (noop, tiny, real, broken)
        ),
    }
    payload = {
        "probe": "probe2-noop-not-improvement",
        "unit_id": "IMP-0372",
        "pass": all(checks.values()),
        "checks": checks,
        "band_width": band["width"],
        "band_source": band["source"],
        "noop": {
            "verdict": noop["verdict"],
            "delta": noop["delta"],
            "reason": noop["reason"],
            "compared_against": noop["compared_against"],
        },
        "tiny": {
            "verdict": tiny["verdict"],
            "delta": tiny["delta"],
            "would_pass_vs_zero": tiny["would_pass_vs_zero"],
            "outside_band": tiny["outside_band"],
        },
        "real": {
            "verdict": real["verdict"],
            "delta": real["delta"],
            "outside_band": real["outside_band"],
            "compared_against": real["compared_against"],
            "origin_unchanged": real["isolation"]["origin_unchanged"],
        },
        "broken": {"verdict": broken["verdict"], "reason": broken["reason"]},
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        failed = [k for k, v in checks.items() if not v]
        return fail(f"checks failed: {failed}")
    print(
        "SUCCESS:IMP-0372-probe2 no-op NOT-IMPROVEMENT; real gain outside "
        f"measured band (width={band['width']:.6f}); tiny vs-zero trap held"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
