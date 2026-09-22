"""Tests for probes/generic.py — the source-agnostic fallback probe."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes.generic import GenericLogfileProbe  # noqa: E402

_P = GenericLogfileProbe()


class TestRatios:
    def test_ratio_frontier(self):
        r = _P.parse(["Compiling 3/40", "Compiling 12/40"])
        assert r.done == 12.0
        assert r.total == 40.0
        assert r.frontier == 12.0

    def test_ratio_frontier_not_last(self):
        r = _P.parse(["step 30/40", "step 5/40"])
        assert r.done == 30.0

    def test_ratio_overshoot(self):
        r = _P.parse(["41/40"])
        assert r.fraction() == 41.0 / 40.0


class TestPercents:
    def test_percent_when_no_ratio(self):
        r = _P.parse(["Receiving objects: 42%", "Receiving objects: 88%"])
        assert r.done == 88.0
        assert r.total == 100.0
        assert r.fraction() == 0.88

    def test_percent_float(self):
        r = _P.parse(["progress 12.5%"])
        assert r.done == 12.5

    def test_ratio_wins_over_percent(self):
        r = _P.parse(["7/10 at 70%"])
        assert r.total == 10.0  # ratio path taken, not the percent path


class TestGpuTerminalNone:
    def test_gpu_and_terminal(self):
        r = _P.parse(["[prog] GPU busy", "10/10", "done"])
        assert r.gpu == "GPU busy"
        assert r.terminal is True

    def test_terminal_without_progress(self):
        r = _P.parse(["build finished"])
        assert r.terminal is True
        assert r.done is None

    def test_no_signal(self):
        r = _P.parse(["just logging along"])
        assert r.done is None
        assert r.total is None
        assert r.terminal is False
        assert r.gpu == ""


class TestTerminalPatternOverride:
    """``terminal_pattern`` pins DONE to a per-task marker line.

    Logs full of incidental "done" words (conda spinners, R's per-package
    ``DONE (pkg)`` lines) otherwise flag terminal=True while the install
    is still running — measured live on the biomni E1 log.
    """

    def test_override_suppresses_builtin_words(self):
        r = _P.parse(["done", "DONE (ggplot2)", "downloading 3/40"], terminal_pattern="Setup Completed")
        assert r.terminal is False

    def test_override_matches_real_completion(self):
        r = _P.parse(
            ["done", "DONE (lme4)", "=== Biomni Environment Setup Completed! ==="],
            terminal_pattern="Setup Completed",
        )
        assert r.terminal is True

    def test_override_regex_semantics(self):
        r = _P.parse(["DATALAKE-DONE"], terminal_pattern=r"DATALAKE-\w+")
        assert r.terminal is True

    def test_no_override_keeps_builtin_behavior(self):
        r = _P.parse(["done"])
        assert r.terminal is True
