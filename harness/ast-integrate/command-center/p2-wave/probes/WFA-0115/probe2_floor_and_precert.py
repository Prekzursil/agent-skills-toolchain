#!/usr/bin/env python3
"""Probe 2: variance-floor INCONCLUSIVE is not a pass; gate precedes certification.

Re-runs the both-states control (reviewer requirement) then checks:
  * inside-floor fusion is INCONCLUSIVE, not PASS/CLEAR/REJECT
  * raw-points mutant would REJECT that same fixture (floor is load-bearing)
  * certification without the gate is refused
  * INCONCLUSIVE refuses certification
  * post-certification gate call is refused
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0115-fused-worse-than-source-detector.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0115-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0115" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    states = D.both_states()
    if not states["discriminates"]:
        return fail("reviewer both-states re-run did not discriminate")
    print(
        f"reviewer both-states good={states['known_good']['verdict']} "
        f"broken={states['known_broken']['verdict']} ok"
    )

    live = D.evaluate(D.fixture_inconclusive_near_best())
    raw = D.evaluate(D.fixture_inconclusive_near_best(), use_raw_points=True)
    print(
        f"inconclusive live={live['verdict']} raw_mutant={raw['verdict']} "
        f"floor={live['variance_floor']} abs_vs_best={live['abs_delta_vs_best']} "
        f"within_best={live['within_floor_of_best']} "
        f"raw_below_all={raw['below_all_sources_beyond_floor']}"
    )
    if live["verdict"] != D.INCONCLUSIVE:
        return fail(f"inside-floor fusion verdict {live['verdict']} want INCONCLUSIVE")
    if live["verdict"] in {"PASS", "CLEAR"}:
        return fail("inside-floor fusion must not be a pass")
    if live.get("pass_claimed"):
        return fail("INCONCLUSIVE claimed pass")
    if not live["within_floor_of_best"]:
        return fail("fixture is not actually inside the floor of the best source")
    if live["used_raw_point_scores"]:
        return fail("live inconclusive path used raw point scores")
    if raw["verdict"] != D.REJECT:
        return fail(
            f"raw-points mutant verdict {raw['verdict']} want REJECT "
            "(floor must be load-bearing)"
        )
    if live["verdict"] == raw["verdict"]:
        return fail("floor path and raw-points mutant returned the same verdict")

    complement = D.evaluate(D.fixture_complementary_not_worse_than_all())
    print(f"complement verdict={complement['verdict']} (must not over-fire FC-11333)")
    if complement["verdict"] != D.CLEAR:
        return fail(f"complement fusion over-fired: {complement['verdict']}")

    incomplete = D.evaluate(D.fixture_incomplete_arm())
    print(f"incomplete verdict={incomplete['verdict']}")
    if incomplete["verdict"] != D.REFUSE:
        return fail("missing fusion case must be refused, never dropped")

    ordering = D.ordering_controls()
    print(
        f"order without_gate={ordering['certify_without_gate']['raised']} "
        f"after_reject={ordering['certify_after_reject']['raised']} "
        f"after_inconclusive={ordering['certify_after_inconclusive']['raised']} "
        f"after_clear={not ordering['certify_after_clear']['raised']} "
        f"post_cert_gate={ordering['gate_after_certification']['raised']}"
    )
    if not ordering["pass"]:
        return fail("pre-certification ordering controls failed")
    if ordering["certify_after_inconclusive"].get("verdict") != D.INCONCLUSIVE:
        return fail("INCONCLUSIVE was treated as a certification pass")

    rec_incon = (doc.get("matched_comparisons") or {}).get("inconclusive") or {}
    if rec_incon.get("verdict") != D.INCONCLUSIVE:
        return fail("artifact inconclusive verdict drifted")
    mutant = doc.get("raw_point_mutant") or {}
    if mutant.get("floor_prevents_raw_reject") is not True:
        return fail("artifact does not record floor-vs-raw mutant")
    if (doc.get("gate_ordering") or {}).get("pass") is not True:
        return fail("artifact gate_ordering.pass is not true")
    det = doc.get("detector") or {}
    if det.get("runs_when") != "before_certification":
        return fail("artifact detector.runs_when is not before_certification")
    if det.get("comparison_against") != "measured_variance_floor":
        return fail("artifact does not declare variance-floor comparison")

    print("SUCCESS:WFA-0115-probe2 floor INCONCLUSIVE and pre-certification order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
