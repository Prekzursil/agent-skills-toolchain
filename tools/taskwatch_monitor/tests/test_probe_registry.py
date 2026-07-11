"""Tests for probes/registry.py — parser-name → probe resolution."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes.base import ProbeError  # noqa: E402
from probes.registry import PROBES, get_probe, probe_for  # noqa: E402


class TestRegistry:
    def test_all_three_registered(self):
        assert set(PROBES) == {"fep-databricks", "bpmd-modal", "generic-logfile"}

    def test_probe_for_hit(self):
        probe = probe_for("fep-databricks")
        assert probe is not None
        assert probe.name == "fep-databricks"

    def test_probe_for_miss(self):
        assert probe_for("nope") is None

    def test_get_probe_hit(self):
        assert get_probe("bpmd-modal").name == "bpmd-modal"

    def test_get_probe_miss(self):
        with pytest.raises(ProbeError, match="unknown parser"):
            _ = get_probe("mystery")
