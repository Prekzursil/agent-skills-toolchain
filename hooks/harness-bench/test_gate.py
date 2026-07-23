#!/usr/bin/env python
"""Tests for the five-run routing regression gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gate  # noqa: E402


def _counts(skill_hit=13, mcp_hit=3, neg_fire=0, skill_total=14):
    return {
        "skill_hit": skill_hit,
        "skill_total": skill_total,
        "mcp_hit": mcp_hit,
        "mcp_total": 5,
        "neg_fire": neg_fire,
        "neg_total": 2,
    }


def _probe(skill_hit=13, mcp_hit=3, neg_fire=0, skill_total=14):
    result = _counts(skill_hit, mcp_hit, neg_fire, skill_total)
    outcomes = []
    for case_id in range(skill_total):
        outcomes.append(
            {
                "case": case_id,
                "skill_hit": case_id < skill_hit,
                "mcp_hit": (case_id < mcp_hit) if case_id < 5 else None,
                "negative_fire": None,
            }
        )
    for offset in range(2):
        outcomes.append(
            {
                "case": skill_total + offset,
                "skill_hit": None,
                "mcp_hit": None,
                "negative_fire": offset < neg_fire,
            }
        )
    result["case_outcomes"] = outcomes
    return result


def _raw(result):
    return json.dumps({"hybrid": result})


def _runner(results):
    iterator = iter(results)
    calls = []

    def run():
        calls.append(True)
        return _raw(next(iterator))

    return run, calls


def test_deterministic_regression_exits_nonzero_only_after_five_runs(capsys):
    # Known-broken: bench ran once and returned 0 for every regression.
    runner, calls = _runner([_probe(skill_hit=12)] * 5)

    rc = gate.run_gate(
        eval_runner=runner,
        baseline_loader=lambda: _counts(),
        backend_down=lambda: False,
    )

    assert rc == 1
    assert len(calls) == 5
    assert "FAILED:routing-regression deterministic-runs=5" in capsys.readouterr().out


def test_equal_aggregates_with_a_case_flip_are_nondeterministic(capsys):
    # Known-broken: no five-run or case-level determinism comparison existed.
    stable = _probe(skill_hit=12)
    flipped = _probe(skill_hit=12)
    flipped["case_outcomes"][0]["skill_hit"] = False
    flipped["case_outcomes"][12]["skill_hit"] = True
    runner, calls = _runner([stable, stable, stable, stable, flipped])

    rc = gate.run_gate(
        eval_runner=runner,
        baseline_loader=lambda: _counts(),
        backend_down=lambda: False,
    )

    assert rc == 0
    assert len(calls) == 5
    assert (
        "NO-GATE:routing-regression nondeterministic runs=5" in capsys.readouterr().out
    )


def test_deterministic_clean_result_passes_after_five_runs(capsys):
    # Known-broken: the only production entry point sampled the evaluator once.
    runner, calls = _runner([_probe()] * 5)

    rc = gate.run_gate(
        eval_runner=runner,
        baseline_loader=lambda: _counts(),
        backend_down=lambda: False,
    )

    assert rc == 0
    assert len(calls) == 5
    assert "PASS:routing-regression deterministic-runs=5" in capsys.readouterr().out


def test_negative_false_fire_is_a_regression(capsys):
    # Known-broken: bench ignored neg_fire even though baseline.json recorded it.
    runner, _calls = _runner([_probe(neg_fire=1)] * 5)

    rc = gate.run_gate(
        eval_runner=runner,
        baseline_loader=lambda: _counts(),
        backend_down=lambda: False,
    )

    assert rc == 1
    assert "negative-fire 0/2->1/2" in capsys.readouterr().out


def test_changed_corpus_totals_never_block(capsys):
    # Known-broken: bench compared hit counts without validating corpus denominators.
    runner, _calls = _runner([_probe(skill_hit=13, skill_total=15)] * 5)

    rc = gate.run_gate(
        eval_runner=runner,
        baseline_loader=lambda: _counts(),
        backend_down=lambda: False,
    )

    assert rc == 0
    assert "corpus-totals-changed" in capsys.readouterr().out


def test_backend_outage_never_blocks(capsys):
    # Known-broken for this lane: no blocking gate existed to constrain on outage.
    runner, _calls = _runner([_probe(skill_hit=12)] * 5)

    rc = gate.run_gate(
        eval_runner=runner,
        baseline_loader=lambda: _counts(),
        backend_down=lambda: True,
    )

    assert rc == 0
    assert "semantic-backend-down" in capsys.readouterr().out


def test_invalid_eval_fails_open_without_trusting_partial_probe(capsys):
    # Known-broken for this lane: there was no five-sample validator or gate diagnostic.
    runner, calls = _runner([_counts()])

    rc = gate.run_gate(
        eval_runner=runner,
        baseline_loader=lambda: _counts(),
        backend_down=lambda: False,
    )

    assert rc == 0
    assert len(calls) == 1
    assert "invalid-eval run=1" in capsys.readouterr().out
