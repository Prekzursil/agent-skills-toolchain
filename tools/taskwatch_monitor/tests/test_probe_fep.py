"""Tests for probes/fep.py — the FEP+ multisim driver-log probe."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes.fep import FepDatabricksProbe  # noqa: E402

_P = FepDatabricksProbe()


class TestWindows:
    def test_complex_and_solvent_legs_sum(self):
        lines = [
            "Stage 5 of 8: replica exchange",
            "complex leg",
            "lambda window 8/12",
            "solvent leg",
            "lambda window 5/12",
        ]
        r = _P.parse(lines)
        assert r.done == 13.0  # 8 (complex frontier) + 5 (solvent frontier)
        assert r.total == 24.0  # 12 + 12
        assert r.phase == "stage 5/8"
        assert r.frontier == 13.0

    def test_frontier_not_distinct_count(self):
        # A rolled tail shows window 10 then 2; frontier is 10, not 2, not count.
        lines = ["complex leg", "window 10/12", "window 2/12"]
        r = _P.parse(lines)
        assert r.done == 10.0

    def test_overshoot_not_capped(self):
        # grill S6: window past its denominator survives as fraction > 1.
        lines = ["complex leg", "window 14/12"]
        r = _P.parse(lines)
        assert r.done == 14.0
        assert r.total == 12.0
        assert r.fraction() == 14.0 / 12.0

    def test_window_without_leg_marker_defaults_complex(self):
        r = _P.parse(["lambda window 3/12"])
        assert r.done == 3.0
        assert r.phase == "fep"

    def test_leg_label_when_no_stage(self):
        r = _P.parse(["solvent leg", "window 4/10"])
        assert r.phase == "solvent leg"


class TestStage:
    def test_stage_without_total(self):
        r = _P.parse(["Stage 3: setup"])
        assert r.phase == "stage 3"
        assert r.done is None

    def test_stage_with_total(self):
        r = _P.parse(["stage 2 of 8"])
        assert r.phase == "stage 2/8"


class TestEdges:
    def test_edge_map_fallback(self):
        lines = ["edges banked 6/8", "edge 2/8"]
        r = _P.parse(lines)
        assert r.done == 6.0  # frontier of the edge map
        assert r.total == 8.0
        assert r.phase == "edges"

    def test_edge_map_with_stage_phase(self):
        r = _P.parse(["Stage 1 of 4", "edges banked 3/8"])
        assert r.phase == "stage 1/4"


class TestGpuAndTerminal:
    def test_gpu_heartbeat_captured(self):
        r = _P.parse(["[prog] GPU 0 util 98%", "window 1/12", "complex leg"])
        assert r.gpu == "GPU 0 util 98%"
        assert "GPU 0 util 98%" in r.detail

    def test_terminal_on_out_fmp(self):
        r = _P.parse(["edge_bac_phe_out.fmp written"])
        assert r.terminal is True
        assert r.done is None

    def test_terminal_on_ddg(self):
        r = _P.parse(["Bennett ddG = +5.2", "complex leg", "window 12/12"])
        assert r.terminal is True

    def test_no_signal_at_all(self):
        r = _P.parse(["initialising harness"])
        assert r.done is None
        assert r.phase == ""
        assert r.terminal is False
        assert r.gpu == ""
