#!/usr/bin/env python3
"""Named probe 1: Brier/log scores match a hand-computed fixture; warm ranking matches.

Two independent score readings:
  1. Arithmetic table in fixtures/hand_computed.json (authored, not imported from the selector)
  2. Recomputed in this probe from the warm-store forecasts
The selector output must match both. A self-import of select_calibrated.brier_score is not a second signal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

TOL = 1e-12


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0268-probe1 {msg}")
    return 1


def close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL


def main() -> int:
    S.require_receipt()
    if not S.MODULE.is_file():
        return fail("select_calibrated.py missing")
    hand = S.load_json(S.HAND)
    store = S.load_json(S.WARM)
    expected_brier = hand["brier"]
    expected_rank = hand["ranking_brier"]

    indep_brier = {}
    indep_log = {}
    for pid in S.CANDIDATES:
        fc = S.forecasts_from_store(store, pid)
        if len(fc) != 12:
            return fail(f"{pid} forecast count {len(fc)} want=12")
        indep_brier[pid] = S.independent_brier(fc)
        indep_log[pid] = S.independent_log(fc)
        if not close(indep_brier[pid], float(expected_brier[pid])):
            return fail(
                f"hand table vs independent recompute {pid}: "
                f"hand={expected_brier[pid]} indep={indep_brier[pid]}"
            )

    indep_rank_brier = sorted(S.CANDIDATES, key=lambda p: (indep_brier[p], p))
    indep_rank_log = sorted(S.CANDIDATES, key=lambda p: (indep_log[p], p))
    if indep_rank_brier != expected_rank:
        return fail(f"independent brier rank {indep_rank_brier} want={expected_rank}")

    sel = S.load_selector()
    warm = sel.select_calibrated(S.CANDIDATES, S.WARM, metric="brier", min_resolved=10)
    if warm.get("strategy_used") != "calibration":
        return fail(f"warm strategy {warm.get('strategy_used')}")
    if warm.get("degradation") is not None:
        return fail("warm run emitted degradation")
    if not warm.get("confident_ranking"):
        return fail("warm run not confident_ranking")
    if warm.get("ranking") != expected_rank:
        return fail(f"selector rank {warm.get('ranking')} want={expected_rank}")

    by_id = {row["participant_id"]: row for row in warm.get("score_table") or []}
    for pid in S.CANDIDATES:
        got = float(by_id[pid]["score"])
        if not close(got, indep_brier[pid]):
            return fail(f"selector brier {pid}={got} indep={indep_brier[pid]}")
        if not close(got, float(expected_brier[pid])):
            return fail(f"selector brier {pid}={got} hand={expected_brier[pid]}")

    warm_log = sel.select_calibrated(S.CANDIDATES, S.WARM, metric="log", min_resolved=10)
    if warm_log.get("ranking") != indep_rank_log:
        return fail(f"log rank {warm_log.get('ranking')} want={indep_rank_log}")
    by_log = {row["participant_id"]: row for row in warm_log.get("score_table") or []}
    for pid in S.CANDIDATES:
        got = float(by_log[pid]["score"])
        if not close(got, indep_log[pid]):
            return fail(f"selector log {pid}={got} indep={indep_log[pid]}")

    seated = [s["participant_id"] for s in warm.get("seated") or []]
    if seated != expected_rank:
        return fail(f"seated {seated}")

    print(
        json.dumps(
            {
                "probe": "probe1-score-fixture",
                "unit_id": "IMP-0268",
                "hand_brier": expected_brier,
                "independent_brier": indep_brier,
                "independent_log": indep_log,
                "selector_ranking_brier": warm.get("ranking"),
                "selector_ranking_log": warm_log.get("ranking"),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0268-probe1 score fixture and warm-store ranking")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
