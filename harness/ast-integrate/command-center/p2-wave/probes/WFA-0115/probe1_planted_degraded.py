#!/usr/bin/env python3
"""Probe 1: planted degraded fusion is REJECT; good fusion is CLEAR (both-states)."""
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
    print(f"FAILED:WFA-0115-probe1 {msg}")
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
    if str(doc.get("record_type") or doc.get("kind") or "") != "RegressionFixture":
        return fail("record_type is not RegressionFixture")

    live = D.both_states()
    good = live["good"]
    broken = live["broken"]
    print(
        f"good verdict={good['verdict']} blocked={good['blocks_certification']} "
        f"floor={good['variance_floor']} mean_delta={good['mean_delta_vs_source']}"
    )
    print(
        f"broken verdict={broken['verdict']} blocked={broken['blocks_certification']} "
        f"below_all={broken['below_all_sources_beyond_floor']} "
        f"mean_delta={broken['mean_delta_vs_source']}"
    )
    print(f"discriminates={live['discriminates']}")

    if not live["discriminates"]:
        return fail("both-states did not discriminate")
    if good["verdict"] != D.CLEAR:
        return fail(f"good fusion verdict {good['verdict']} want CLEAR")
    if broken["verdict"] != D.REJECT:
        return fail(f"planted degraded verdict {broken['verdict']} want REJECT")
    if good["blocks_certification"]:
        return fail("good fusion must not block certification on this axis")
    if not broken["blocks_certification"]:
        return fail("degraded fusion must block certification")
    if broken.get("pass_claimed"):
        return fail("REJECT claimed pass")
    if len(broken.get("per_case") or []) != 8:
        return fail("degraded per-case deltas not listed for all matched cases")
    if len(good.get("per_case") or []) != 8:
        return fail("good per-case deltas not listed for all matched cases")
    if set(broken["mean_delta_vs_source"]) != {"source-strong", "source-weak"}:
        return fail("per-source deltas missing")
    for sid, delta in broken["mean_delta_vs_source"].items():
        if delta >= 0:
            return fail(f"degraded fusion delta vs {sid} is not negative: {delta}")
    if not broken["floor_measured_before_comparison"]:
        return fail("variance floor was not measured before comparison")
    if broken["used_raw_point_scores"]:
        return fail("live gate used raw point scores")

    rec_bs = doc.get("both_states") or {}
    if rec_bs.get("discriminates") is not True:
        return fail("artifact both_states.discriminates is not true")
    rec_broken = rec_bs.get("known_broken") or {}
    rec_good = rec_bs.get("known_good") or {}
    if rec_broken.get("verdict") != D.REJECT:
        return fail("artifact known_broken is not REJECT")
    if rec_good.get("verdict") != D.CLEAR:
        return fail("artifact known_good is not CLEAR")
    planted = doc.get("planted_fixture") or {}
    if planted.get("caught") is not True:
        return fail("artifact planted_fixture.caught is not true")
    if doc.get("per_source_deltas_listed") is not True:
        return fail("artifact per_source_deltas_listed is not true")

    comps = doc.get("matched_comparisons") or {}
    rec_deg = comps.get("degraded") or {}
    if rec_deg.get("verdict") != broken["verdict"]:
        return fail("artifact degraded verdict drifted from live")
    if abs(float(rec_deg.get("fusion_mean") or 0) - float(broken["fusion_mean"])) > 1e-12:
        return fail("artifact fusion_mean drifted from live")

    print("SUCCESS:WFA-0115-probe1 planted degraded both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
