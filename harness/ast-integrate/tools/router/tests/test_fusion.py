#!/usr/bin/env python3
"""Tests for tools/router/fusion.py and tools/router/corpus.py (IMP-0391).

Runs under pytest or as a script (``python3 -B tools/router/tests/test_fusion.py``
exits 0 when every test passes).
"""
from __future__ import annotations

import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import corpus  # noqa: E402
import fusion  # noqa: E402


def _close(a, b, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol


def test_tolerance_is_shared_with_corpus() -> None:
    assert fusion.CALIBRATION_TOLERANCE == corpus.CALIBRATION_TOLERANCE == 0.15


def test_linear_fuse_is_clipped_and_weighted() -> None:
    assert fusion.linear_fuse(1.0, 1.0, 0.65, 0.35) == 1.0
    assert fusion.linear_fuse(0.0, 0.0, 0.65, 0.35) == 0.0
    assert fusion.linear_fuse(0.5, 0.5, -0.65, -0.35) == 0.0
    assert _close(fusion.linear_fuse(0.8, 0.4, 0.5, 0.5), 0.6)


def test_rrf_prefers_agreement_and_is_total_order() -> None:
    fused = fusion.fuse_rankings(["a", "b", "c"], ["b", "a", "d"])
    ids = [cid for cid, _ in fused]
    assert set(ids) == {"a", "b", "c", "d"}
    # deterministic stage carries more weight: a (det rank 1) beats b (det rank 2)
    assert ids[0] == "a"
    # a candidate ranked by only one stage scores below one ranked by both
    scores = dict(fused)
    assert scores["c"] < scores["a"] and scores["d"] < scores["b"]
    assert fused == fusion.fuse_rankings(["a", "b", "c"], ["b", "a", "d"])


def test_reliability_diagram_hand_example() -> None:
    scored = [(0.9, 1), (0.9, 1), (0.9, 0), (0.1, 0), (0.45, 0), (0.55, 1)]
    diag = fusion.reliability_diagram(scored)
    bins = diag["bins"]
    assert [b["n"] for b in bins] == [1, 0, 2, 0, 3]
    top = bins[-1]
    assert _close(top["predicted"], 0.9) and _close(top["observed_accuracy"], 2 / 3)
    assert _close(top["delta"], abs(2 / 3 - 0.9))
    assert diag["named_outlier_bins"] == [top]  # 0.233 > 0.15; the 0.5 bin is exact
    assert diag["band_0_9"] == [top]
    assert bins[1]["observed_accuracy"] is None and bins[1]["delta"] is None
    assert _close(fusion.brier_score(scored), (0.01 + 0.01 + 0.81 + 0.01 + 0.2025 + 0.2025) / 6)
    assert fusion.log_loss(scored) > 0


def test_calibrator_maps_fused_score_to_bin_accuracy() -> None:
    cal = corpus.fit_calibrator(**corpus.PROD_WEIGHTS)
    assert cal["edges"] == list(fusion.BIN_EDGES)
    assert sum(cal["counts"]) == len(corpus.labelled_rows()) == 80
    assert corpus.calibrate(0.99, cal) == cal["values"][-1] == 1.0
    assert corpus.calibrate(0.0, cal) == cal["values"][0] == 0.0
    assert corpus.calibrate(-3.0, cal) == cal["values"][0]  # clipped, not an error


def test_production_bins_within_tolerance() -> None:
    report = corpus.evaluate(**corpus.PROD_WEIGHTS)
    assert report["within_tolerance"], report["named_outlier_bins"]
    assert report["band_0_9_occupied"] and report["band_0_9_within_tolerance"]
    assert report["accuracy"] >= 0.75
    assert report["n"] == 80 and len(report["per_query"]) == 80
    # the raw fused score, displayed as a probability, would NOT pass
    raw = fusion.calibration_report(fusion.score_pairs(corpus._pairs(), **corpus.PROD_WEIGHTS))
    assert raw["named_outlier_bins"], "raw score is already calibrated; the calibrator would be idle"


def test_mutant_weight_moves_a_bin() -> None:
    report = corpus.production_report()
    control = report["mutation"]
    assert control["production_outlier_count"] == 0
    assert control["mutant_outlier_count"] >= 1
    assert control["mutant_moves_a_bin_outside_tolerance"]
    assert control["mutant_accuracy_drops"]
    assert report["mutant"]["accuracy"] < report["production"]["accuracy"]


def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:  # pragma: no cover - reported, not raised
            failed += 1
            print(f"FAIL {name}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
