"""Shared live measurements for IMP-0318 probes and receipt emission."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.antifail.unanimity import (  # noqa: E402
    REMEDIATION_ORDER,
    evaluate,
    outcome_change_rate,
)
from fixtures import (  # noqa: E402
    canonical_contested,
    canonical_correct_instant,
    canonical_late_legitimate,
    canonical_planted_wrong,
    rate_corpus,
)

MODULE_REL = "tools/council/antifail/unanimity.py"


def _expect(result, fixture: dict[str, Any], enabled: bool = True) -> dict[str, Any]:
    fired = bool(result.fired)
    want_fire = bool(fixture.get("expected_trigger")) and enabled
    want_first = fixture.get("expected_first_outcome")
    want_final = (
        fixture.get("expected_first_outcome")
        if not enabled
        else fixture.get("expected_final_outcome")
    )
    ok = (
        fired == want_fire
        and result.first_outcome == want_first
        and result.final_outcome == want_final
        and result.outcome_changed == (result.final_outcome != result.first_outcome)
    )
    if enabled and fired:
        executed = list(result.remediation.get("executed") or [])
        ok = ok and executed == list(REMEDIATION_ORDER)
        ok = ok and result.remediation.get("blinded_from_first_pass_votes") is True
        ok = ok and result.remediation.get("recruited_critic", {}).get("id") == "recruited-critic"
        ok = ok and bool(result.remediation.get("forced_dissenter_id"))
    return {
        "council_id": result.council_id,
        "family": result.family or fixture.get("family"),
        "ok": ok,
        "fired": fired,
        "would_have_fired": result.would_have_fired,
        "first_outcome": result.first_outcome,
        "final_outcome": result.final_outcome,
        "outcome_changed": result.outcome_changed,
        "expected_trigger": want_fire,
        "expected_first": want_first,
        "expected_final": want_final,
        "executed": list(result.remediation.get("executed") or []),
        "counterexample_id": (result.remediation.get("counterexample") or {}).get("id"),
    }


def measure() -> dict[str, Any]:
    planted = canonical_planted_wrong()
    correct = canonical_correct_instant()
    late = canonical_late_legitimate()
    contested = canonical_contested()

    r_planted = evaluate(planted)
    r_correct = evaluate(correct)
    r_late = evaluate(late)
    r_contested = evaluate(contested)
    r_disabled = evaluate(planted, enabled=False)

    corpus = rate_corpus()
    corpus_results = [evaluate(row) for row in corpus]
    rate = outcome_change_rate(corpus_results)
    planted_rows = [
        r for r, src in zip(corpus_results, corpus) if src["family"] == "planted-wrong"
    ]
    correct_rows = [
        r for r, src in zip(corpus_results, corpus) if src["family"] == "correct-instant"
    ]
    planted_flipped = all(r.fired and r.outcome_changed for r in planted_rows)
    correct_survived = all(
        r.fired and (not r.outcome_changed) and r.final_outcome == r.first_outcome
        for r in correct_rows
    )
    all_triggered = all(r.fired for r in corpus_results)

    planted_row = _expect(r_planted, planted)
    correct_row = _expect(r_correct, correct)
    late_row = _expect(r_late, late)
    contested_row = _expect(r_contested, contested)
    disabled_ok = (
        (not r_disabled.fired)
        and r_disabled.would_have_fired
        and r_disabled.final_outcome == planted["expected_first_outcome"]
        and (not r_disabled.outcome_changed)
        and r_planted.outcome_changed
        and r_planted.final_outcome != r_disabled.final_outcome
    )

    theatre = (not any(r.outcome_changed for r in planted_rows)) and all(
        r.fired for r in planted_rows
    )

    return {
        "module": MODULE_REL,
        "canonical": {
            "planted_wrong": planted_row,
            "correct_instant": correct_row,
            "late_legitimate": late_row,
            "contested": contested_row,
            "trigger_disabled": {
                "ok": disabled_ok,
                "fired": r_disabled.fired,
                "would_have_fired": r_disabled.would_have_fired,
                "first_outcome": r_disabled.first_outcome,
                "final_outcome": r_disabled.final_outcome,
                "enabled_final": r_planted.final_outcome,
                "disabled_final": r_disabled.final_outcome,
                "outcomes_differ": r_planted.final_outcome != r_disabled.final_outcome,
            },
        },
        "rate": rate,
        "corpus": {
            "n": len(corpus_results),
            "planted_wrong_n": len(planted_rows),
            "correct_instant_n": len(correct_rows),
            "all_triggered": all_triggered,
            "planted_wrong_all_overturned": planted_flipped,
            "correct_instant_all_survived": correct_survived,
            "theatre": theatre,
            "rows": [
                {
                    "council_id": r.council_id,
                    "family": src["family"],
                    "fired": r.fired,
                    "first_outcome": r.first_outcome,
                    "final_outcome": r.final_outcome,
                    "outcome_changed": r.outcome_changed,
                }
                for r, src in zip(corpus_results, corpus)
            ],
        },
        "pass": bool(
            planted_row["ok"]
            and correct_row["ok"]
            and late_row["ok"]
            and contested_row["ok"]
            and disabled_ok
            and all_triggered
            and planted_flipped
            and correct_survived
            and (not theatre)
            and rate.get("rate_status") == "measured"
            and rate.get("triggered") == 20
            and rate.get("changed") == 12
            and rate.get("rate") == 12 / 20
        ),
    }
