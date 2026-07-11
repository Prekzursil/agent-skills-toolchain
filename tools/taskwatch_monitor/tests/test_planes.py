"""Tests for core/planes.py — liveness plane, progress plane, BLIND state."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.models import PollResult  # noqa: E402
from core.planes import (  # noqa: E402
    PROGRESS_SCHEMA,
    BlindState,
    LivenessMonitor,
    LivenessSample,
    ProgressTracker,
    _changed,
)


def _sample(
    ts: float,
    *,
    exists: bool = True,
    mtime: float | None = 5.0,
    size: int | None = 10,
    lines: int = 1,
) -> LivenessSample:
    return LivenessSample(
        ts=ts, exists=exists, mtime=mtime, size=size, line_count=lines
    )


class TestLivenessSample:
    def test_from_poll(self):
        poll = PollResult(
            exists=True, mtime=9.0, lines=["a", "b"], size=42, liveness=True
        )
        sample = LivenessSample.from_poll(3.0, poll)
        assert sample.ts == 3.0
        assert sample.exists is True
        assert sample.mtime == 9.0
        assert sample.size == 42
        assert sample.line_count == 2


class TestChanged:
    def test_mtime_advance(self):
        assert _changed(_sample(0, mtime=5.0), _sample(1, mtime=6.0)) is True

    def test_size_advance_when_mtime_flat(self):
        prev = _sample(0, mtime=5.0, size=10)
        cur = _sample(1, mtime=5.0, size=20)
        assert _changed(prev, cur) is True

    def test_line_advance_when_mtime_size_flat(self):
        prev = _sample(0, mtime=5.0, size=10, lines=1)
        cur = _sample(1, mtime=5.0, size=10, lines=2)
        assert _changed(prev, cur) is True

    def test_exists_transition(self):
        prev = _sample(0, exists=True, mtime=5.0, size=10, lines=1)
        cur = _sample(1, exists=False, mtime=5.0, size=10, lines=1)
        assert _changed(prev, cur) is True

    def test_no_change(self):
        prev = _sample(0, mtime=None, size=None, lines=1)
        cur = _sample(1, mtime=None, size=None, lines=1)
        assert _changed(prev, cur) is False


class TestLivenessMonitor:
    def test_full_lifecycle(self):
        mon = LivenessMonitor(stall_after_s=10.0)

        first = mon.update(_sample(0.0, lines=1))
        assert first.reason == "first-sample"
        assert first.progressing is True

        changed = mon.update(_sample(1.0, lines=2))
        assert changed.reason == "changed"
        assert changed.progressing is True

        idle = mon.update(_sample(2.0, lines=2))
        assert idle.reason == "idle"
        assert idle.stalled is False

        stalled = mon.update(_sample(20.0, lines=2))
        assert stalled.reason == "stalled"
        assert stalled.stalled is True
        assert stalled.last_change_ts == 1.0

    def test_first_sample_absent_not_progressing(self):
        mon = LivenessMonitor(stall_after_s=5.0)
        verdict = mon.update(_sample(0.0, exists=False))
        assert verdict.progressing is False


class TestProgressTracker:
    def _rec(self, **over: object) -> dict[str, object]:
        base: dict[str, object] = {
            "schema": PROGRESS_SCHEMA,
            "done": 2.0,
            "total": 10.0,
            "phase": "run",
            "ts": 1.0,
            "seq": 1,
        }
        base.update(over)
        return base

    def test_accepts_and_advances(self):
        t = ProgressTracker()
        r1 = t.ingest(self._rec(seq=1, done=2.0))
        assert r1.accepted is True
        assert r1.snapshot is not None and r1.snapshot.done == 2.0
        r2 = t.ingest(self._rec(seq=2, done=5.0))
        assert r2.accepted is True
        assert t.last is not None and t.last.done == 5.0

    def test_stale_seq_rejected_keeps_last(self):
        t = ProgressTracker()
        _ = t.ingest(self._rec(seq=5, done=9.0))
        stale = t.ingest(self._rec(seq=5, done=3.0))
        assert stale.accepted is False
        assert stale.reason == "stale-seq"
        assert stale.snapshot is not None and stale.snapshot.done == 9.0

    def test_bad_schema(self):
        t = ProgressTracker()
        r = t.ingest(self._rec(schema="other/9"))
        assert r.accepted is False
        assert r.reason == "bad-schema"

    def test_bad_seq_non_int(self):
        assert ProgressTracker().ingest(self._rec(seq="x")).reason == "bad-seq"

    def test_bad_seq_bool(self):
        assert ProgressTracker().ingest(self._rec(seq=True)).reason == "bad-seq"

    def test_bad_done(self):
        assert ProgressTracker().ingest(self._rec(done="nope")).reason == "bad-done"

    def test_bad_done_bool(self):
        assert ProgressTracker().ingest(self._rec(done=True)).reason == "bad-done"

    def test_bad_ts(self):
        assert ProgressTracker().ingest(self._rec(ts="nope")).reason == "bad-ts"

    def test_unknown_total_accepted(self):
        r = ProgressTracker().ingest(self._rec(total=None))
        assert r.accepted is True
        assert r.snapshot is not None and r.snapshot.total is None
        assert r.snapshot.fraction() is None

    def test_non_str_phase_coerced_empty(self):
        r = ProgressTracker().ingest(self._rec(phase=5))
        assert r.snapshot is not None and r.snapshot.phase == ""


class TestBlindState:
    def test_observe_ok_then_blind(self):
        state = BlindState()
        ok = PollResult(exists=True, mtime=5.0, lines=["a"], liveness=True)
        state.observe(100.0, ok)
        assert state.blind is False
        assert state.last_poll is ok
        assert state.age(150.0) == 50.0

        bad = PollResult(exists=False, mtime=None, error="boom")
        state.observe(160.0, bad)
        assert state.blind is True
        assert state.consecutive_errors == 1
        assert state.history == ["boom"]
        # last good poll is retained, age keeps counting from last OK
        assert state.last_poll is ok
        assert state.age(200.0) == 100.0

    def test_age_none_when_never_ok(self):
        assert BlindState().age(10.0) is None
