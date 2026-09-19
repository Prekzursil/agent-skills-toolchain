"""CC-0004 tests_required: planted / legitimate-import / use-vs-mention."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
sys.path.insert(0, str(PROBE))

import fanin_detector as det  # noqa: E402

FIXTURES = PROBE / "fixtures"
PLANTED = FIXTURES / "planted_local_predicate.py"
GOOD = FIXTURES / "good_shared_import.py"
PROSE = FIXTURES / "prose_mention_fork.md"


def test_planted_local_predicate_reported_with_file_line() -> None:
    """Known-broken control: planted local predicate must be reported with file:line."""
    report = det.scan_paths([PLANTED], repo=REPO)
    assert report.local_predicates, report.to_dict()
    lines = {f.file_line for f in report.local_predicates}
    # At least one finding must cite planted_local_predicate.py:<lineno>
    planted_hits = [f for f in report.local_predicates if f.path.endswith(
        "fixtures/planted_local_predicate.py"
    )]
    assert planted_hits, f"planted file not reported: {lines}"
    for f in planted_hits:
        assert f.line > 0, f
        assert ":" in f.file_line
        assert f.file_line.split(":")[-1].isdigit()
    symbols = {f.symbol for f in planted_hits}
    assert symbols & {"is_complete", "evaluate"}, symbols


def test_legitimate_shared_import_site_found() -> None:
    """Known-present control: the legitimate single import site must be found."""
    report = det.scan_paths([GOOD], repo=REPO)
    assert report.shared_imports, report.to_dict()
    assert not report.local_predicates, report.to_dict()
    paths = {f.path for f in report.shared_imports}
    assert any(p.endswith("fixtures/good_shared_import.py") for p in paths)
    assert any(
        "completion_predicate" in f.detail or f.symbol in {"evaluate", "completion_predicate", "REDUCER_ID"}
        for f in report.shared_imports
    )


def test_prose_mention_of_fork_is_not_reported() -> None:
    """Use-vs-mention: documenting the fork in prose must NOT be reported."""
    report = det.scan_paths([PROSE, FIXTURES], repo=REPO)
    # prose path recorded as skipped non-python, never as local_predicate
    assert any(s.endswith("prose_mention_fork.md") for s in report.skipped_non_python) or (
        PROSE.as_posix() not in {f.path for f in report.local_predicates}
    )
    prose_hits = [
        f
        for f in report.local_predicates
        if f.path.endswith("prose_mention_fork.md")
    ]
    assert prose_hits == [], prose_hits


def test_both_states_planted_fires_and_good_is_silent() -> None:
    """Evidence control: FIRES on planted scratch, SILENT on clean good+prose set."""
    bad = det.scan_paths([PLANTED], repo=REPO)
    assert bad.local_predicates, "detector silent on planted fork measures nothing"

    clean = det.scan_paths([GOOD, PROSE], repo=REPO)
    assert clean.shared_imports, "matcher must see the legitimate import"
    assert clean.local_predicates == [], clean.to_dict()
    assert clean.ok_clean is True


def test_live_tree_finds_coordination_shared_import() -> None:
    """Live known-present: platform/coordination/reducer.py imports the shared symbol."""
    report = det.scan(
        roots=["platform/coordination/reducer.py"],
        repo=REPO,
        excludes=(),
    )
    assert report.files_scanned == 1
    assert report.shared_imports, report.to_dict()
    assert any(
        f.path.endswith("platform/coordination/reducer.py") for f in report.shared_imports
    )
