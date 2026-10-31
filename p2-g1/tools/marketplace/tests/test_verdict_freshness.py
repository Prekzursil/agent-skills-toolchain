#!/usr/bin/env python3
"""IMP-0095 verdict-freshness test suite (standalone runner).

Roster recovered from the delivery receipt: 9 named tests covering both
independent decay signals (input-hash, age), the negative control, the
recompute rule and the reviewer obligation (STALE never renders as PASS).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "marketplace"))

from freshness import (  # noqa: E402
    AGE_STALE,
    HASH_STALE,
    STALE,
    VALID,
    Clock,
    age_sweep,
    age_invalidated,
    enumerate_surfaces,
    evaluate_freshness,
    hash_inputs,
    hash_invalidated,
    recompute_if_stale,
    render_api,
    render_record,
    stamp_verdict,
    summary_view,
    surface_result,
)

BASE = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)

INPUTS = {
    "conformance_pass_rate": 1.0,
    "docs_complete": True,
    "provenance_present": True,
    "sbom_present": True,
    "tests_pass_rate": 1.0,
    "tests_present": True,
}


def _record(clock=None, **kw):
    return stamp_verdict(
        "quality_score",
        "CLEAN",
        dict(INPUTS),
        clock=clock or Clock(BASE),
        subject="fixture.pkg@1.0.0",
        freshness_window=kw.pop("freshness_window", timedelta(days=30)),
        **kw,
    )


def test_input_change_marks_stale():
    rec = _record()
    mutated = dict(INPUTS)
    mutated["sbom_present"] = False
    state = evaluate_freshness(rec, mutated, Clock(BASE))
    assert state["freshness"] == STALE, state
    assert state["hash_signal"] == STALE
    assert state["age_signal"] == VALID
    assert HASH_STALE in state["reasons"]


def test_age_alone_marks_stale():
    rec = _record()
    later = Clock(BASE + timedelta(days=31))
    state = evaluate_freshness(rec, dict(INPUTS), later)
    assert state["freshness"] == STALE, state
    assert state["age_signal"] == STALE
    assert state["hash_signal"] == VALID
    assert AGE_STALE in state["reasons"]


def test_fresh_unchanged_inputs_stay_valid():
    rec = _record()
    state = evaluate_freshness(rec, dict(INPUTS), Clock(BASE))
    assert state["freshness"] == VALID, state
    assert state["hash_signal"] == VALID and state["age_signal"] == VALID


def test_hash_and_age_signals_are_independent():
    rec = _record()
    mutated = dict(INPUTS)
    mutated["sbom_present"] = False
    # hash path never inspects the clock: no clock passed, still STALE
    assert hash_invalidated(rec, mutated) is True
    assert hash_invalidated(rec, dict(INPUTS)) is False
    # age path never inspects the hashes: clock far future, hashes untouched
    assert age_invalidated(rec, Clock(BASE + timedelta(days=400))) is True
    assert age_invalidated(rec, Clock(BASE)) is False
    assert rec.input_hashes == hash_inputs(INPUTS)


def test_missing_hashes_are_stale():
    rec = _record()
    partial = dict(INPUTS)
    partial["advisory_extra"] = "new-input"
    state = evaluate_freshness(rec, partial, Clock(BASE))
    assert state["freshness"] == STALE, state
    assert state["hash_signal"] == STALE


def test_recompute_on_stale_and_skip_when_valid():
    calls = {"n": 0}

    def recompute(inputs):
        calls["n"] += 1
        return "RECOMPUTED"

    rec = _record()
    out, did = recompute_if_stale(rec, dict(INPUTS), recompute, Clock(BASE))
    assert did is False and calls["n"] == 0 and out.result == "CLEAN"

    out, did = recompute_if_stale(
        rec, dict(INPUTS), recompute, Clock(BASE + timedelta(days=31))
    )
    assert did is True and calls["n"] == 1 and out.result == "RECOMPUTED"
    assert out.freshness == VALID


def test_stale_never_rendered_as_pass():
    surfaces = {s["surface"] for s in enumerate_surfaces()}
    assert surfaces == {
        "surface_result.result_shown",
        "render_record.result_shown",
        "render_api.verdict",
        "summary_view.pass",
    }
    rec = _record()
    rec.freshness = STALE
    sr = surface_result(rec)
    rr = render_record(rec)
    ra = render_api(rec)
    assert sr["result_shown"] == STALE and sr["pass"] is False
    assert rr["result_shown"] == STALE and rr["pass"] is False
    assert ra["verdict"] == STALE


def test_summary_does_not_count_stale_as_pass():
    fresh = _record()
    stale = _record()
    stale.freshness = STALE
    view = summary_view([fresh, stale])
    assert view["pass"] == 1, view
    assert view["stale"] == 1
    assert view["stale_never_pass"] is True


def test_conformance_hash_only_still_ages_when_window_set():
    rec = stamp_verdict(
        "conformance_result",
        "PASS",
        {"checks_passed": 58},
        clock=Clock(BASE),
        subject="conformance/paper-a",
        freshness_window=timedelta(hours=24),
    )
    later = Clock(BASE + timedelta(hours=25))
    state = evaluate_freshness(rec, {"checks_passed": 58}, later)
    assert state["freshness"] == STALE, state
    assert state["age_signal"] == STALE and state["hash_signal"] == VALID
    swept = age_sweep([rec], later)
    assert swept["swept"] == ["conformance/paper-a"]
    assert rec.freshness == STALE


TESTS = [
    test_input_change_marks_stale,
    test_age_alone_marks_stale,
    test_fresh_unchanged_inputs_stay_valid,
    test_hash_and_age_signals_are_independent,
    test_missing_hashes_are_stale,
    test_recompute_on_stale_and_skip_when_valid,
    test_stale_never_rendered_as_pass,
    test_summary_does_not_count_stale_as_pass,
    test_conformance_hash_only_still_ages_when_window_set,
]


def main() -> int:
    for t in TESTS:
        t()
        print(f"PASS {t.__name__}")
    print(f"SUCCESS:IMP-0095-tests {len(TESTS)}/{len(TESTS)}")
    print("SUCCESS:IMP-0095")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
