#!/usr/bin/env python3
"""Tests for CC-0023 owner option-id adjudication controls."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
MOD_PATH = REPO / "command-center/lib/owner_option_id_adjudication.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "owner_option_id_adjudication", MOD_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["owner_option_id_adjudication"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def adj():
    return _load()


def test_all_58_end_deferred_or_answered_with_impact(adj, tmp_path):
    led = adj.apply_owner_silence(now="2026-09-08T02:00:00Z")
    assert led["counts"]["total_refs"] == 58
    assert led["counts"]["deferred"] == 58
    assert led["counts"]["owner_answered"] == 0
    assert led["recorded_owner_answers"] == []
    assert led["honesty"]["invented_owner_answers"] is False
    ctrl = adj.deferred_coverage_control(led)
    assert ctrl.passed, ctrl.detail
    for rid, st in led["ref_states"].items():
        assert st["state"] == "DEFERRED"
        assert st["owner_answer"] is None
        assert st["answered_at"] is None
        assert st["impact"]


def test_zero_silent_rewrites_unattributed_change_fails(adj):
    before = "BLOCKS: A6; M-16, M-18"
    after_silent = "BLOCKS: A6; MECH-16, MECH-18"
    bad = adj.silent_rewrite_control(before_text=before, after_text=after_silent)
    assert bad.passed is False
    good = adj.silent_rewrite_control(before_text=before, after_text=before)
    assert good.passed is True
    attributed = adj.silent_rewrite_control(
        before_text=before,
        after_text=after_silent,
        attributed_spans=[("M-16", "MECH-16"), ("M-18", "MECH-18")],
    )
    # attributed path: bare sequence changed but pairs provided — still check
    # our control flags unattributed only; with pairs, removed-bare should pass.
    assert attributed.detail["unattributed"] == [] or attributed.passed


def test_grouping_batches_shared_decisions(adj):
    ctrl = adj.grouping_control()
    assert ctrl.passed, ctrl.detail
    assert ctrl.detail["n_questions_declared"] == 12
    assert ctrl.detail["n_questions_used_by_refs"] == 7
    assert ctrl.detail["n_questions_used_by_refs"] < 58


def test_durability_roundtrip_empty_owner_answers(adj, tmp_path):
    led = adj.apply_owner_silence(now="2026-09-08T02:00:00Z")
    decisions = tmp_path / "OWNER-DECISIONS.md"
    decisions.write_text("# OWNER-DECISIONS\n\n", encoding="utf-8")
    adj.upsert_owner_decisions_section(led, path=decisions)
    ctrl = adj.durability_roundtrip(led, decisions_path=decisions)
    assert ctrl.passed, ctrl.detail
    assert ctrl.detail["expected_owner_answers"] == 0
    text = decisions.read_text(encoding="utf-8")
    assert "OQ-CC23-01" in text
    assert "DEFERRED" in text
    # Re-read recovers zero invented answers.
    assert "None. Owner session unavailable" in text or "_None." in text


def test_owner_answer_accepted_only_with_provenance(adj, tmp_path):
    """Fabricated-looking answers without provenance=owner stay DEFERRED."""
    fake = {
        "schema_version": 1,
        "unit": "CC-0023",
        "answers": {
            "OQ-CC23-01": {
                "owner_answer": "leave mentions",
                "answered_at": "2026-09-08T01:00:00Z",
                # missing provenance=owner
            }
        },
        "ref_states": {},
        "recorded_owner_answers": [],
    }
    led = adj.apply_owner_silence(ledger=fake, now="2026-09-08T02:00:00Z")
    assert led["counts"]["owner_answered"] == 0
    assert led["counts"]["deferred"] == 58

    real = {
        "schema_version": 1,
        "unit": "CC-0023",
        "answers": {
            "OQ-CC23-01": {
                "owner_answer": "leave all 10 mentions untouched",
                "answered_at": "2026-09-08T03:00:00Z",
                "provenance": "owner",
            }
        },
        "ref_states": {},
        "recorded_owner_answers": [],
    }
    led2 = adj.apply_owner_silence(ledger=real, now="2026-09-08T02:00:00Z")
    assert led2["counts"]["owner_answered"] == 10
    assert led2["counts"]["deferred"] == 48
    assert len(led2["recorded_owner_answers"]) == 1
    decisions = tmp_path / "OWNER-DECISIONS.md"
    decisions.write_text("# OWNER-DECISIONS\n", encoding="utf-8")
    adj.upsert_owner_decisions_section(led2, path=decisions)
    ctrl = adj.durability_roundtrip(led2, decisions_path=decisions)
    assert ctrl.passed, ctrl.detail


def test_census_arithmetic_matches_resolution(adj):
    ctrl = adj.census_arithmetic_ok()
    assert ctrl.passed, ctrl.detail
    census = adj.load_census()
    assert len(census["refs"]) == 58
    assert census["requires_author_adjudication"] == 58
