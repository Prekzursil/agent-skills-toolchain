#!/usr/bin/env python3
"""Unit tests for CC-0021 option-id namespace registry + gate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
MOD_PATH = REPO / "tools/command-center/option_id_namespace.py"
PROBE = REPO / "command-center/p2-wave/probes/CC-0021"
PLANTED = PROBE / "fixtures/planted-bare-m16.md"
MENTION = PROBE / "fixtures/mention-collision-quote.md"


def _load():
    spec = importlib.util.spec_from_file_location("option_id_namespace", MOD_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["option_id_namespace"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ns():
    return _load()


def test_known_present_all_20_deep_research_m16(ns):
    hits, files = ns.deep_research_m16_census()
    assert len(hits) == 20
    assert len(files) == 16
    assert all(h.token == "M-16" for h in hits)


def test_false_positive_mech_not_reported_as_bare(ns):
    sample = "MECH-16 MECH-01 MECH-38"
    assert ns.mech_not_reported_as_bare(sample) is True
    assert ns.extract_bare_m_ids(sample) == set()
    doc13 = (
        REPO
        / "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix/13-ARCHITECTURE-CANDIDATES.md"
    ).read_text(encoding="utf-8")
    assert "MECH-" in doc13
    assert ns.extract_bare_m_ids(doc13) == set()


def test_known_broken_planted_bare_m16_fires_gate(ns):
    assert PLANTED.is_file()
    _report, namespaces = ns.build_registry()
    evaluation = ns.evaluate_paths([PLANTED], namespaces)
    assert evaluation["gate_fire"] is True
    assert evaluation["unresolved_count"] >= 1
    assert any(u["token"] == "M-16" for u in evaluation["unresolved_ambiguous"])


def test_use_vs_mention_quote_not_flagged_unresolved(ns):
    assert MENTION.is_file()
    _report, namespaces = ns.build_registry()
    evaluation = ns.evaluate_paths([MENTION], namespaces)
    assert evaluation["unresolved_count"] == 0
    assert len(evaluation["mentions"]) >= 1


def test_remeasure_arithmetic_33_38_31_7_2(ns):
    report, _ = ns.build_registry()
    assert report.family_m_count == 33
    assert report.doc13_mech_count == 38
    assert report.colliding_count == 31
    assert report.doc13_only_count == 7
    assert report.universe_only_count == 2
    assert report.arithmetic == "33/38/31/7/2"
    assert report.live_shared_bare_count == 0
    assert "BARE_M_RE" in report.regexes
    assert report.regexes["BARE_M_RE"] == ns.BARE_M_RE.pattern


def test_controls_bundle_all_pass(ns):
    payload = ns.run_controls(scratch_planted=PLANTED, mention_doc=MENTION)
    assert payload["ok"] is True
    for name, row in payload["controls"].items():
        assert row["pass"] is True, name
