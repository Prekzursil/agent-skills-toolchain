#!/usr/bin/env python3
"""Unit tests for the CC-0020 two-detector mechanism dedup gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
GATE_PATH = REPO / "tools/command-center/mechanism_dedup_gate.py"
FIXTURES = (
    REPO
    / "command-center/p2-wave/probes/CC-0020/fixtures/planted-mutants.json"
)


def _load_gate():
    spec = importlib.util.spec_from_file_location("mechanism_dedup_gate", GATE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mechanism_dedup_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


@pytest.fixture(scope="module")
def fixtures():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_all_four_planted_mutant_classes_caught(gate, fixtures):
    per = gate.evaluate_mutants(fixtures["seed"], fixtures["mutants"])
    assert set(per) >= {
        "exact_rename",
        "paraphrase",
        "one_parameter_fork",
        "full_rewrite",
    }
    for cls, row in per.items():
        assert row["detection_rate"] == 1.0, cls
        assert row["caught"] is True, cls
        assert row["error_direction"] is None, cls


def test_full_rewrite_defeats_lexical_but_embedding_fires(gate, fixtures):
    row = gate.compare(fixtures["seed"], fixtures["mutants"]["full_rewrite"])
    assert row["lexical_jaccard"] <= 0.24
    assert row["lexical_fire"] is False
    assert row["embedding_fire"] is True
    assert row["verdict"] == "CONTESTED"
    assert row["caught"] is True


def test_zero_false_merges_on_hand_verified_distinct_set(gate, fixtures):
    units = fixtures["distinct_units"]
    assert len(units) >= 24
    rep = gate.evaluate_distinct_set(units)
    assert rep["false_merge_count"] == 0
    assert rep["false_merges"] == []


def test_error_direction_classifies_every_disagreement(gate, fixtures):
    per = gate.evaluate_mutants(fixtures["seed"], fixtures["mutants"])
    for cls, row in per.items():
        # Agreement => None; if we ever miss, must be under-merge.
        if row["error_direction"] is not None:
            assert row["error_direction"] in ("over-merge", "under-merge"), cls

    distinct = gate.evaluate_distinct_set(fixtures["distinct_units"])
    for d in distinct["disagreements"]:
        assert d["error_direction"] in ("over-merge", "under-merge")
        assert d["verdict"] in ("MERGE", "CONTESTED")


def test_determinism_same_pair_same_verdict(gate, fixtures):
    det = gate.determinism_check(
        fixtures["seed"], fixtures["mutants"]["full_rewrite"], runs=7
    )
    assert det["deterministic"] is True
    assert len(set(det["verdicts"])) == 1
    assert det["threshold_variance"]["lexical"] == 0.0
    assert det["threshold_variance"]["embedding"] == 0.0


def test_and_gate_requires_both_fires_for_merge(gate):
    # Synthetic: high lexical, low embedding -> CONTESTED not MERGE
    a = "alpha beta gamma delta epsilon zeta"
    b = "alpha beta gamma delta epsilon eta"
    # Force thresholds
    scored = gate.compare(
        a,
        b,
        lexical_threshold=0.5,
        embedding_threshold=0.999,
    )
    assert scored["lexical_fire"] is True
    assert scored["embedding_fire"] is False
    assert scored["verdict"] == "CONTESTED"
