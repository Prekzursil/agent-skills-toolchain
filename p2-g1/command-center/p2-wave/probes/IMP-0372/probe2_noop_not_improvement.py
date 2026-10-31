#!/usr/bin/env python3
"""IMP-0372 probe2: a no-op candidate must NOT be reported as an improvement.

Independent adversarial reviewer probe. Starts from the receipt's catalog
negative controls (C1/C2/C3) and measures its OWN null-change band - it never
reuses probe1's table or trusts the author's summary. It then runs four
candidates through measure_candidate on the same harness:

  C1  noop              files={}                  -> NOT-IMPROVEMENT inside-measured-band
  C2  tiny delta        score.base "100.1"        -> NOT-IMPROVEMENT, yet would_pass_vs_zero=True
  real candidate        score.base "120"          -> IMPROVEMENT outside-measured-band
  C3  regression-broken score.base "not-a-number" -> NOT-IMPROVEMENT reason=regression-failed

Every classification is compared against the MEASURED band, never against zero
(compared_against_zero stays False). Any IMPROVEMENT verdict on C1/C2/C3, or a
NOT-IMPROVEMENT verdict on the real candidate, is a reviewer FAIL. The host
tree is never touched: the subject repo is a throwaway tempdir and the
worktree/copy isolation never writes back to it (origin_unchanged asserted).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from selfimprove.measure import (  # noqa: E402
    Harness,
    measure_candidate,
    measure_null_change,
)

RECEIPT = REPO / "command-center/receipts/IMP-0372.json"

NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

REQUIRED_NEGCTLS = (
    "IMP-0372-C1-noop-candidate",
    "IMP-0372-C2-tiny-delta-would-pass-vs-zero",
    "IMP-0372-C3-regression-broken-after-state",
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0372-probe2 {msg}")
    return 1


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared:{doc.get('state')}")
    nctl_ids = {n.get("id") for n in doc.get("negative_controls") or []}
    missing = [want for want in REQUIRED_NEGCTLS if want not in nctl_ids]
    if missing:
        return fail(f"receipt-negctl-missing:{','.join(missing)}")

    with tempfile.TemporaryDirectory() as td:
        origin = Path(td)
        (origin / "score.base").write_text("100\n", encoding="utf-8")
        band_row = measure_null_change(origin, harness=Harness(), parent=origin,
                                       label="probe2-reviewer-band")
        band = band_row["noise_band"]
        if band["assumed"] is not False or band["compared_against_zero"] is not False:
            return fail("band-not-measured")
        if band["width"] <= 0.1:
            return fail(f"band-too-narrow:{band['width']}")

        noop = measure_candidate(origin, candidate_id="C1-noop", files={},
                                 harness=Harness(), band=band, parent=origin)
        tiny = measure_candidate(origin, candidate_id="C2-tiny",
                                 files={"score.base": "100.1\n"},
                                 harness=Harness(), band=band, parent=origin)
        real = measure_candidate(origin, candidate_id="real",
                                 files={"score.base": "120\n"},
                                 harness=Harness(), band=band, parent=origin)
        broken = measure_candidate(origin, candidate_id="C3-broken",
                                   files={"score.base": "not-a-number\n"},
                                   harness=Harness(), band=band, parent=origin)

    checks = {
        "noop_not_improvement": (
            noop["verdict"] == "NOT-IMPROVEMENT"
            and noop["reason"] == "inside-measured-band"
        ),
        "noop_delta_zero": noop["delta"] == 0.0,
        "noop_vs_zero_false": noop["would_pass_vs_zero"] is False,
        "tiny_not_improvement": (
            tiny["verdict"] == "NOT-IMPROVEMENT"
            and tiny["reason"] == "inside-measured-band"
        ),
        "tiny_would_pass_vs_zero": tiny["would_pass_vs_zero"] is True,
        "tiny_inside_band": tiny["outside_band"] is False,
        "tiny_delta_matches": abs(tiny["delta"] - 0.1) < 1e-9,
        "real_improvement": (
            real["verdict"] == "IMPROVEMENT"
            and real["reason"] == "outside-measured-band"
        ),
        "real_outside_band": real["outside_band"] is True,
        "real_delta_matches": abs(real["delta"] - 20.0) < 1e-9,
        "regression_broken_refused": (
            broken["verdict"] == "NOT-IMPROVEMENT"
            and broken["reason"] == "regression-failed"
        ),
        "band_not_zero_everywhere": all(
            row["compared_against_zero"] is False
            for row in (noop, tiny, real, broken)
        ),
        "origin_unchanged_everywhere": all(
            row["isolation"]["origin_unchanged"] is True
            for row in (noop, tiny, real, broken)
        ),
    }
    bad = [name for name, ok in checks.items() if not ok]
    if bad:
        return fail("checks:" + ",".join(bad))

    print(json.dumps({
        "band": {"assumed": False, "n": band["n"], "width": band["width"]},
        "broken": {"reason": broken["reason"], "verdict": broken["verdict"]},
        "checks": checks,
        "noop": {"delta": noop["delta"], "reason": noop["reason"],
                 "verdict": noop["verdict"]},
        "pass": True,
        "probe": "probe2-noop-not-improvement",
        "real": {"delta": real["delta"], "origin_unchanged": True,
                 "outside_band": True, "verdict": real["verdict"]},
        "tiny": {"delta": tiny["delta"], "outside_band": tiny["outside_band"],
                 "verdict": tiny["verdict"],
                 "would_pass_vs_zero": tiny["would_pass_vs_zero"]},
        "unit_id": "IMP-0372",
    }, sort_keys=True))
    print("SUCCESS:IMP-0372-probe2 no-op/tiny/broken refused; real improvement "
          "outside measured band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
