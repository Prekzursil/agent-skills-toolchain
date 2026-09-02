"""Tests for core/models.py — TaskSpec, TaskStatus, ProgressSnapshot, EtaEstimate, PollResult."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.models import (  # noqa: E402
    EtaEstimate,
    PollResult,
    ProgressSnapshot,
    Provenance,
    TaskSpec,
    TaskStatus,
)


class TestTaskStatus:
    def test_from_str_valid(self):
        assert TaskStatus.from_str("running") == TaskStatus.RUNNING
        assert TaskStatus.from_str("  DONE ") == TaskStatus.DONE

    def test_from_str_unknown_is_blind(self):
        assert TaskStatus.from_str("nonsense") == TaskStatus.BLIND


class TestTaskSpec:
    def test_history_key_defaults_to_adapter(self):
        spec = TaskSpec(id="a", adapter="http-json")
        assert spec.history_key == "http-json"

    def test_history_key_uses_task_type_when_set(self):
        spec = TaskSpec(id="a", adapter="http-json", task_type="fep")
        assert spec.history_key == "fep"

    def test_to_dict(self):
        spec = TaskSpec(
            id="a",
            adapter="local-file-tail",
            parser="p",
            notify=["terminal"],
            remediate=True,
            config={"path": "/x"},
        )
        d = spec.to_dict()
        assert d["id"] == "a"
        assert d["notify"] == ["terminal"]
        assert d["remediate"] is True
        assert d["task_type"] == "local-file-tail"
        assert d["config"] == {"path": "/x"}


class TestProgressSnapshot:
    def _snap(self, done: float, total: float | None) -> ProgressSnapshot:
        return ProgressSnapshot(
            schema="s", done=done, total=total, phase="p", ts=1.0, seq=1
        )

    def test_fraction_unknown_total(self):
        assert self._snap(5.0, None).fraction() is None

    def test_fraction_nonpositive_total(self):
        assert self._snap(5.0, 0.0).fraction() is None

    def test_fraction_in_range(self):
        assert self._snap(2.0, 4.0).fraction() == 0.5

    def test_fraction_overshoot_not_clamped(self):
        assert self._snap(6.0, 4.0).fraction() == 1.5

    def test_to_dict(self):
        d = self._snap(2.0, 4.0).to_dict()
        assert d["done"] == 2.0
        assert d["fraction"] == 0.5


class TestEtaEstimate:
    def test_estimable_true(self):
        eta = EtaEstimate(p50=1.0, p90=2.0, provenance=Provenance.MEASURED)
        assert eta.estimable is True
        assert eta.to_dict()["provenance"] == "measured"

    def test_estimable_false_when_p50_none(self):
        eta = EtaEstimate(p50=None, p90=None, provenance=Provenance.NONE)
        assert eta.estimable is False

    def test_estimable_false_when_only_p90_none(self):
        eta = EtaEstimate(p50=1.0, p90=None, provenance=Provenance.MEASURED)
        assert eta.estimable is False


class TestPollResult:
    def test_blind_false_without_error(self):
        pr = PollResult(exists=True, mtime=1.0, lines=["a"], liveness=True)
        assert pr.blind is False
        assert pr.to_dict()["line_count"] == 1

    def test_blind_true_with_error(self):
        pr = PollResult(exists=False, mtime=None, error="boom")
        assert pr.blind is True
        assert pr.to_dict()["error"] == "boom"
