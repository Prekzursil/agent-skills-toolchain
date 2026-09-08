"""Pytest + both-states controls for the vacuous-test AST detector (TST-0348)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from vacuous_detector import (  # noqa: E402
    VACUOUS_CLASSES,
    detect,
    scan_roots,
)

FIXTURES = ROOT / "fixtures"
PLANTED = FIXTURES / "planted_vacuous"
KNOWN_GOOD = FIXTURES / "known_good"
BROKEN = FIXTURES / "both_states" / "broken"
FIXED = FIXTURES / "both_states" / "fixed"


def test_both_states_control_fires_on_vacuous_silent_on_good():
    """Catalog both-states: vacuous FAIL (fire) / non-vacuous PASS (silent)."""
    bad = detect(BROKEN)
    good = detect(FIXED)
    assert bad, f"detector silent on broken vacuous fixture: {bad!r}"
    assert not good, f"detector fired on fixed genuine fixture: {good!r}"


def test_planted_controls_each_vacuous_class_detected():
    report = scan_roots([PLANTED], repo=REPO)
    found_classes = {f.vacuous_class for f in report.findings}
    missing = set(VACUOUS_CLASSES) - found_classes
    assert not missing, (
        f"planted controls missed classes {missing}; "
        f"found={sorted(found_classes)}; findings={report.findings}"
    )
    # Every planted test should be flagged at least once
    planted_tests = {
        "test_no_assertion_mention_only",
        "test_constant_assertion_literal",
        "test_mock_configured_assertion_only",
        "test_swallowed_failure_bare",
    }
    flagged = {f.test_name for f in report.findings}
    assert planted_tests <= flagged, (
        f"unflagged planted tests: {planted_tests - flagged}"
    )


def test_string_mention_of_assert_is_not_an_assertion():
    report = scan_roots([PLANTED], repo=REPO)
    no_assert = [
        f
        for f in report.findings
        if f.test_name == "test_no_assertion_mention_only"
        and f.vacuous_class == "no_assertion"
    ]
    assert no_assert, (
        "mention-only test must be classified no_assertion (AST, not text)"
    )


def test_known_good_zero_false_positives():
    report = scan_roots([KNOWN_GOOD], repo=REPO)
    assert report.findings == [], (
        f"false positives on known-good sample: {report.findings}"
    )
    assert report.tests_scanned >= 3
    assert report.vacuous_test_count == 0


def test_coverage_excluding_vacuous_reported():
    report = scan_roots([PLANTED, KNOWN_GOOD], repo=REPO)
    d = report.to_dict()
    assert d["headline_test_count"] == d["tests_scanned"]
    assert d["vacuous_test_count"] > 0
    assert d["non_vacuous_test_count"] > 0
    assert d["headline_coverage_pct"] == 100.0
    assert d["coverage_excluding_vacuous_pct"] < d["headline_coverage_pct"]
    assert d["coverage_excluding_vacuous_pct"] == round(
        100.0 * d["non_vacuous_test_count"] / d["headline_test_count"], 4
    )
    assert "file_line_list" in d and d["file_line_list"]
    assert set(d["class_counts"]) == set(VACUOUS_CLASSES)


def test_detect_api_truthy_on_broken():
    assert detect(BROKEN)
    assert detect(FIXED) == []
