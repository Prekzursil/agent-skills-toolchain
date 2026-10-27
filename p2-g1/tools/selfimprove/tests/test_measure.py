"""Directly-runnable tests for IMP-0372 (selfimprove.measure)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (str(REPO / "tools"),):
    if p not in sys.path:
        sys.path.insert(0, p)

from selfimprove.measure import (  # noqa: E402
    Harness,
    classify_delta,
    measure_candidate,
    measure_null_change,
)


def test_null_change_band_is_measured() -> None:
    with tempfile.TemporaryDirectory() as td:
        origin = Path(td)
        (origin / "score.base").write_text("100\n", encoding="utf-8")
        out = measure_null_change(origin, harness=Harness(), parent=origin,
                                  label="unit-test")
        band = out["noise_band"]
        assert band["assumed"] is False
        assert band["source"] == "measured-null-change"
        assert band["n"] >= 6
        assert band["width"] >= 0.0
        assert out["compared_against"] == "measured-band"


def test_noop_not_improvement() -> None:
    with tempfile.TemporaryDirectory() as td:
        origin = Path(td)
        (origin / "score.base").write_text("100\n", encoding="utf-8")
        out = measure_null_change(origin, harness=Harness(), parent=origin)
        cand = measure_candidate(origin, candidate_id="noop", files={},
                                 harness=Harness(), band=out["noise_band"],
                                 parent=origin)
        assert cand["verdict"] == "NOT-IMPROVEMENT"
        assert cand["reason"] in ("inside-measured-band", "regression-failed")


def test_real_improvement_outside_band() -> None:
    with tempfile.TemporaryDirectory() as td:
        origin = Path(td)
        (origin / "score.base").write_text("100\n", encoding="utf-8")
        out = measure_null_change(origin, harness=Harness(), parent=origin)
        cand = measure_candidate(origin, candidate_id="real",
                                 files={"score.base": "150\n"},
                                 harness=Harness(), band=out["noise_band"],
                                 parent=origin)
        assert cand["verdict"] == "IMPROVEMENT"
        assert cand["outside_band"] is True


def test_tiny_delta_refused_by_band_but_would_pass_vs_zero() -> None:
    row = classify_delta(0.3, {"width": 0.4})
    assert row["outside_band"] is False
    assert row["would_pass_vs_zero"] is True
    assert row["verdict"] == "NOT-IMPROVEMENT"
    assert row["compared_against"] == "measured-band"


def test_regression_broken_refused() -> None:
    with tempfile.TemporaryDirectory() as td:
        origin = Path(td)
        (origin / "score.base").write_text("100\n", encoding="utf-8")
        out = measure_null_change(origin, harness=Harness(), parent=origin)
        cand = measure_candidate(origin, candidate_id="broken",
                                 files={"score.base": "not-a-number\n"},
                                 harness=Harness(), band=out["noise_band"],
                                 parent=origin)
        assert cand["verdict"] == "NOT-IMPROVEMENT"
        assert cand["reason"] == "regression-failed"


if __name__ == "__main__":
    import traceback

    failed = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failed.append(name)
                print(f"FAIL {name}")
                traceback.print_exc()
    if failed:
        print(f"FAILED:IMP-0372-tests failures={len(failed)}")
        raise SystemExit(1)
    print("SUCCESS:IMP-0372-tests all pass")
    raise SystemExit(0)
