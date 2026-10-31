"""Tests for probes/bpmd.py — the BPMD metadynamics driver-log probe."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes.bpmd import BpmdModalProbe  # noqa: E402

_P = BpmdModalProbe()


class TestTrials:
    def test_trial_frontier(self):
        lines = [
            "setup complete",
            "Trial 1 of 8",
            "metadynamics running",
            "Trial 3 of 8",
        ]
        r = _P.parse(lines)
        assert r.done == 3.0
        assert r.total == 8.0
        assert r.phase == "metadynamics"
        assert r.frontier == 3.0

    def test_slash_form(self):
        r = _P.parse(["trial 5/8"])
        assert r.done == 5.0
        assert r.total == 8.0

    def test_frontier_not_last(self):
        r = _P.parse(["trial 7 of 8", "trial 2 of 8"])
        assert r.done == 7.0

    def test_overshoot_not_capped(self):
        r = _P.parse(["trial 9 of 8"])
        assert r.fraction() == 9.0 / 8.0

    def test_default_phase_when_only_trials(self):
        r = _P.parse(["trial 1 of 8"])
        assert r.phase == "bpmd"


class TestPhaseGpuTerminal:
    def test_phase_only_no_trials(self):
        r = _P.parse(["equilibration step"])
        assert r.done is None
        assert r.phase == "equilibration"

    def test_gpu_heartbeat(self):
        r = _P.parse(["[gpu-util] 0: 95%", "trial 1 of 8"])
        assert r.gpu == "0: 95%"

    def test_terminal_posescore(self):
        r = _P.parse(["trial 8 of 8", "PoseScore = 1.2 A"])
        assert r.terminal is True

    def test_terminal_composite_score(self):
        r = _P.parse(["composite score computed"])
        assert r.terminal is True
        assert r.done is None

    def test_empty(self):
        r = _P.parse(["hello world"])
        assert r.done is None
        assert r.phase == ""
        assert r.terminal is False
        assert r.gpu == ""
