"""Tests for core/history.py — SQLite prior store."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.history import HistoryStore, Prior, _percentile  # noqa: E402


class TestPercentile:
    def test_single_value(self):
        assert _percentile([7.0], 0.9) == 7.0

    def test_interpolates(self):
        assert _percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5

    def test_top_rank_clamped_to_last(self):
        assert _percentile([1.0, 2.0, 3.0], 1.0) == 3.0


class TestHistoryStore:
    def test_record_and_durations(self):
        with HistoryStore() as store:
            store.record("fep", 10.0, ts=1.0)
            store.record("fep", 30.0, ts=2.0)
            store.record("other", 5.0, ts=3.0)
            assert store.durations("fep") == [10.0, 30.0]
            assert store.durations("other") == [5.0]

    def test_prior_none_when_empty(self):
        with HistoryStore() as store:
            assert store.prior("ghost") is None

    def test_prior_summary(self):
        with HistoryStore() as store:
            for d in (10.0, 20.0, 30.0, 40.0, 50.0):
                store.record("fep", d, ts=d)
            prior = store.prior("fep")
            assert prior is not None
            assert prior.count == 5
            assert prior.p50 == 30.0
            assert prior.p90 == 46.0

    def test_prior_single_run(self):
        with HistoryStore() as store:
            store.record("fep", 42.0, ts=1.0)
            prior = store.prior("fep")
            assert prior is not None
            assert prior.p50 == 42.0
            assert prior.p90 == 42.0

    def test_file_backed_persists(self, tmp_path: Path):
        db = str(tmp_path / "h.db")
        store = HistoryStore(db)
        store.record("t", 5.0, ts=1.0)
        store.close()
        reopened = HistoryStore(db)
        assert reopened.durations("t") == [5.0]
        reopened.close()

    def test_prior_to_dict(self):
        d = Prior(task_type="fep", count=3, p50=10.0, p90=20.0).to_dict()
        assert d["task_type"] == "fep"
        assert d["count"] == 3
        assert d["p90"] == 20.0
