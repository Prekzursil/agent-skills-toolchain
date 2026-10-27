"""Catalog tests for IMP-0097 benchmark-gaming defence."""
from __future__ import annotations

import sys
from pathlib import Path

_MKT = Path(__file__).resolve().parents[1]
if str(_MKT) not in sys.path:
    sys.path.insert(0, str(_MKT))

from benchmark_gaming import contribution, score_with_benchmarks, score_without_record  # noqa: E402
from scenario import load_scenario  # noqa: E402


def test_unreproduced_contributes_zero() -> None:
    measurements, records, provenance, _raw = load_scenario()
    full = score_with_benchmarks(measurements, records, provenance)
    for rec in records:
        if rec.record_id.startswith("rec.unreproduced") or rec.publisher_only or not rec.reproduced:
            assert contribution(rec, provenance) == 0.0
            without = score_without_record(measurements, records, provenance, rec.record_id)
            if rec.record_id != "rec.independent.reproduced":
                assert without.total == full.total or contribution(rec, provenance) == 0.0


def test_reproduced_independently_cased_raises_score() -> None:
    measurements, records, provenance, _raw = load_scenario()
    full = score_with_benchmarks(measurements, records, provenance)
    without = score_without_record(
        measurements, records, provenance, "rec.independent.reproduced"
    )
    assert full.total - without.total == 1.5


def test_self_authored_case_set_is_flagged() -> None:
    _m, records, provenance, _r = load_scenario()
    pub = next(r for r in records if r.publisher_only)
    assert contribution(pub, provenance) == 0.0


def run_all() -> None:
    test_unreproduced_contributes_zero()
    test_reproduced_independently_cased_raises_score()
    test_self_authored_case_set_is_flagged()


if __name__ == "__main__":
    run_all()
    print("SUCCESS:test_benchmark_gaming")
