"""Tests for probes/base.py — ProbeReading + parsing helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.models import PollResult  # noqa: E402
from probes.base import (  # noqa: E402
    ProbeReading,
    extract_gpu,
    frontier_of,
    join_detail,
    parse_ratio,
    reading_from_poll,
)


def _reading(done: float | None, total: float | None) -> ProbeReading:
    return ProbeReading(
        done=done,
        total=total,
        phase="p",
        frontier=done,
        gpu="",
        terminal=False,
        detail="",
    )


class TestFraction:
    def test_none_done(self):
        assert _reading(None, 10.0).fraction() is None

    def test_none_total(self):
        assert _reading(3.0, None).fraction() is None

    def test_nonpositive_total(self):
        assert _reading(3.0, 0.0).fraction() is None

    def test_normal(self):
        assert _reading(3.0, 12.0).fraction() == 0.25

    def test_overshoot_not_clamped(self):
        # grill S6a: a frontier past its denominator survives as fraction > 1.
        assert _reading(14.0, 12.0).fraction() == 14.0 / 12.0

    def test_has_progress(self):
        assert _reading(1.0, 2.0).has_progress is True
        assert _reading(None, None).has_progress is False

    def test_to_dict(self):
        d = _reading(3.0, 12.0).to_dict()
        assert d["done"] == 3.0
        assert d["fraction"] == 0.25
        assert d["terminal"] is False


class TestParseRatio:
    def test_match(self):
        assert parse_ratio("edge 3 / 20 done") == (3, 20)

    def test_no_match(self):
        assert parse_ratio("no numbers here") is None


class TestFrontierOf:
    def test_empty(self):
        assert frontier_of([]) is None

    def test_max_not_last_or_count(self):
        # frontier = MAX numerator (10), NOT the last (2) nor a distinct-count (2).
        assert frontier_of([(10, 12), (2, 12)]) == (10, 12)

    def test_max_denominator(self):
        assert frontier_of([(1, 8), (2, 12)]) == (2, 12)


class TestExtractGpu:
    def test_prog_tag(self):
        assert extract_gpu("[prog] GPU 0 util 98%") == "GPU 0 util 98%"

    def test_gpu_util_tag(self):
        assert extract_gpu("[gpu-util] 0: 97%, 1: 95%") == "0: 97%, 1: 95%"

    def test_no_tag(self):
        assert extract_gpu("just a line") is None


class TestJoinDetail:
    def test_drops_empty(self):
        assert join_detail("stage 1/8", "", "GPU 0") == "stage 1/8 · GPU 0"

    def test_all_empty(self):
        assert join_detail("", "") == ""


class TestReadingFromPoll:
    def test_bridges_lines(self):
        seen: list[str] = []

        class Recorder:
            name = "rec"

            def parse(self, lines: list[str]) -> ProbeReading:
                seen.extend(lines)
                return _reading(1.0, 2.0)

        poll = PollResult(exists=True, mtime=1.0, lines=["a", "b"])
        r = reading_from_poll(Recorder(), poll)
        assert r.done == 1.0
        assert seen == ["a", "b"]
