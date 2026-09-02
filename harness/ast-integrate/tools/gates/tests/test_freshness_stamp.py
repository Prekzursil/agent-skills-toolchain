#!/usr/bin/env python3
"""Tests for tools/gates/freshness_stamp.py (TST-0235). Stdlib only; runnable directly."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gates.freshness_stamp import (  # noqa: E402
    FRESH,
    NOT_CHECKED,
    STALE,
    UNDATED_GREEN,
    AdvisoryFixture,
    StoredResult,
    classify,
    evaluate,
    gate_verdict,
    load_policy,
    max_age_seconds,
    measure_fresh_reuse,
    measure_stale_advisory_green,
    naive_read_gate,
)

NOW = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_inclusive_bound() -> None:
    assert classify(_iso(NOW - timedelta(seconds=100)), NOW, 100) == FRESH
    assert classify(_iso(NOW - timedelta(seconds=101)), NOW, 100) == STALE
    assert classify(None, NOW, 100) == UNDATED_GREEN
    assert classify("", NOW, 100) == UNDATED_GREEN
    assert classify(_iso(NOW + timedelta(seconds=5)), NOW, 100) == STALE


def test_stale_green_is_not_checked() -> None:
    policy = load_policy()
    max_age = max_age_seconds("advisory-database", policy)
    stale = StoredResult("PASS", freshness_stamp=_iso(NOW - timedelta(seconds=max_age + 1)))
    assert gate_verdict(stale, NOW, policy) == (NOT_CHECKED, STALE)
    assert naive_read_gate(stale) == "PASS"
    undated = StoredResult("PASS", freshness_stamp=None)
    assert gate_verdict(undated, NOW, policy) == (NOT_CHECKED, UNDATED_GREEN)
    fresh = StoredResult("PASS", freshness_stamp=_iso(NOW - timedelta(seconds=max_age)))
    assert gate_verdict(fresh, NOW, policy) == ("PASS", FRESH)


def test_unknown_source_class_has_zero_max_age() -> None:
    policy = load_policy()
    assert max_age_seconds("no-such-source", policy) == 0
    rec = StoredResult("PASS", "no-such-source", _iso(NOW - timedelta(seconds=1)))
    assert gate_verdict(rec, NOW, policy)[0] == NOT_CHECKED


def test_evaluate_requeries_only_when_stale() -> None:
    fixture = AdvisoryFixture("fixture", findings=["CVE-2026-0001"])
    fresh = StoredResult("PASS", freshness_stamp=_iso(NOW))
    r = evaluate(fresh, fixture, NOW)
    assert r["reused"] and not r["query_invoked"] and r["query_count_delta"] == 0
    assert r["live_verdict"] == "PASS"
    stale = StoredResult("PASS", freshness_stamp=_iso(NOW - timedelta(days=2)))
    r = evaluate(stale, fixture, NOW)
    assert r["before_requery_verdict"] == NOT_CHECKED
    assert r["query_invoked"] and r["query_count_delta"] == 1
    assert r["live_verdict"] == "FAIL" and r["live_findings"] == ["CVE-2026-0001"]
    assert fixture.query_count == 1


def test_measurements_are_deterministic() -> None:
    a, b = measure_fresh_reuse(), measure_fresh_reuse()
    assert a == b and a["pass"] and a["query_count_fresh"] == 0 and a["both_states"]
    c, d = measure_stale_advisory_green(), measure_stale_advisory_green()
    assert c == d and c["pass"] and c["query_count_delta"] == 1
    assert c["before_requery_verdict"] == NOT_CHECKED and c["naive_still_pass"]
    assert c["live_verdict"] == "FAIL" and c["undated_gate_verdict"] == NOT_CHECKED


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    print(f"SUCCESS:freshness-stamp-tests {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
