"""Both-states controls for the work-unit dependency gate.

Every test builds its own in-memory catalog and plants the exact defect shape. The two live-repo
assertions at the bottom read the real catalog but never write it.

WHY THIS GATE EXISTS. `tools/command-center/validate.py` contains no reference to `work_units` at
all -- it validates the 103 register `items` and none of the 2,007 work units, which ARE the
program. Measured consequence: 41 dependency refs resolve to nothing, 876 more point at buckets that
have zero members, and the catalog's own `known_defects_at_merge` describes two of these wrongly and
two more that were fixed long ago. None of it is gated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wudeps as wd  # noqa: E402


def _catalog(units: list[dict]) -> dict:
    return {"work_units": units, "work_units_meta": {}}


def test_fires_on_a_dependency_that_resolves_to_nothing() -> None:
    report = wd.scan(
        _catalog(
            [
                {"id": "A-1", "dependencies": ["A-2"]},
                {"id": "A-2", "dependencies": []},
                {"id": "A-3", "dependencies": ["NOPE"]},
            ]
        )
    )
    assert report["dangling_refs"] == [("A-3", "NOPE")]
    assert report["units_scanned"] == 3


def test_silent_when_every_dependency_resolves() -> None:
    """Both-states pair: the same shape with a real target must produce nothing."""
    report = wd.scan(
        _catalog(
            [
                {"id": "A-1", "dependencies": ["A-2"]},
                {"id": "A-2", "dependencies": []},
            ]
        )
    )
    assert report["dangling_refs"] == []
    assert report["zero_member_bucket_refs"] == []


def test_a_bucket_reference_with_no_members_is_a_finding() -> None:
    """THE defect: B07 carries 297 inbound edges in the live catalog and has zero members."""
    report = wd.scan(
        _catalog(
            [
                {"id": "A-1", "dependencies": ["B07"]},
                {"id": "A-2", "bucket": "B02", "dependencies": ["B02"]},
            ]
        )
    )
    assert report["zero_member_bucket_refs"] == [("A-1", "B07")]
    assert report["bucket_members"]["B02"] == 1
    assert report["bucket_members"]["B07"] == 0


def test_a_bucket_reference_WITH_members_is_not_a_finding() -> None:
    """Discrimination: without this, the gate could 'pass' by flagging every bucket equally."""
    report = wd.scan(
        _catalog(
            [
                {"id": "A-1", "bucket": "B10", "dependencies": []},
                {"id": "A-2", "dependencies": ["B10"]},
            ]
        )
    )
    assert report["zero_member_bucket_refs"] == []


def test_a_self_dependency_is_caught() -> None:
    report = wd.scan(_catalog([{"id": "A-1", "dependencies": ["A-1"]}]))
    assert report["self_dependencies"] == ["A-1"]


def test_a_cycle_is_caught_and_a_dag_is_not() -> None:
    cyclic = wd.scan(
        _catalog(
            [
                {"id": "A", "dependencies": ["B"]},
                {"id": "B", "dependencies": ["A"]},
            ]
        )
    )
    assert cyclic["cycles"], "a 2-cycle must be reported"
    acyclic = wd.scan(
        _catalog(
            [
                {"id": "A", "dependencies": ["B"]},
                {"id": "B", "dependencies": []},
            ]
        )
    )
    assert acyclic["cycles"] == []


def test_scan_fails_closed_on_an_empty_catalog() -> None:
    """Zero units is a broken read, never a clean bill of health (ci-hygiene section 1)."""
    with pytest.raises(ValueError, match="fail closed"):
        wd.scan(_catalog([]))


def test_the_ratchet_passes_at_baseline_and_fails_one_worse() -> None:
    """The gate ratchets: pre-existing debt does not break CI, but adding to it does.

    Demanding an immediate fix for 876 pre-existing edges would either block every unrelated PR or
    get the gate deleted. Freezing the measured count and failing on regression is what actually
    holds the line.
    """
    at_baseline = {
        "dangling_refs": [("x", "y")],
        "zero_member_bucket_refs": [],
        "cycles": [],
        "self_dependencies": [],
    }
    assert (
        wd.regressions(
            at_baseline,
            {
                "dangling_refs": 1,
                "zero_member_bucket_refs": 0,
                "cycles": 0,
                "self_dependencies": 0,
            },
        )
        == []
    )

    worse = {
        "dangling_refs": [("x", "y"), ("p", "q")],
        "zero_member_bucket_refs": [],
        "cycles": [],
        "self_dependencies": [],
    }
    found = wd.regressions(
        worse,
        {
            "dangling_refs": 1,
            "zero_member_bucket_refs": 0,
            "cycles": 0,
            "self_dependencies": 0,
        },
    )
    assert len(found) == 1 and "dangling_refs" in found[0]


def test_the_ratchet_reports_an_improvement_so_the_floor_can_be_lowered() -> None:
    """An unreported improvement is how a ratchet silently stops ratcheting."""
    better = {
        "dangling_refs": [],
        "zero_member_bucket_refs": [],
        "cycles": [],
        "self_dependencies": [],
    }
    assert wd.improvements(
        better,
        {
            "dangling_refs": 1,
            "zero_member_bucket_refs": 0,
            "cycles": 0,
            "self_dependencies": 0,
        },
    )


# --- live catalog: read-only, and the numbers are the ones this session measured ---


def test_the_live_catalog_matches_the_recorded_baseline() -> None:
    report = wd.scan(wd.load())
    assert report["units_scanned"] == 2007
    assert len(report["dangling_refs"]) == wd.BASELINE["dangling_refs"]
    assert (
        len(report["zero_member_bucket_refs"]) == wd.BASELINE["zero_member_bucket_refs"]
    )


def test_the_live_catalog_has_no_cycles_or_self_dependencies() -> None:
    """Both were RECORDED as present in known_defects_at_merge and are measurably fixed.

    `dependency_cycles: 1` and `self_dependencies: [IMP-0274, IMP-0277, IMP-0299]` are stale entries.
    The three named units now depend on IMP-0265/IMP-0264 and nothing self-refers. Pinned here so
    the fix cannot silently regress behind a stale record.
    """
    report = wd.scan(wd.load())
    assert report["cycles"] == []
    assert report["self_dependencies"] == []
