#!/usr/bin/env python3
"""IMP-0456 planted controls: duplicate blocks, gap blocks, clean merges."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog_slice_merge as m  # noqa: E402


MINIMAL_UNIT = {
    "id": "CC-0001",
    "title": "fixture",
    "phase": "0",
    "question_or_target": "fixture target",
    "inputs": [],
    "dependencies": [],
    "assigned_model_vendor_role": {
        "model": "opus",
        "vendor": "anthropic",
        "role": "implementer",
    },
    "tool_permissions": ["Read"],
    "execution_substrate": "local-serialized",
    "timeout_seconds": 60,
    "output_path": "command-center/receipts/CC-0001.json",
    "output_schema": "command-center/schema/receipt.schema.json",
    "evidence_requirement": "fixture",
    "tests_required": ["fixture"],
    "reviewer_requirement": "fixture",
    "completion_sentinel": "SUCCESS:CC-0001",
    "retry_policy": "none",
    "failure_classification": ["overclaim"],
    "owner_approval_required": False,
}

# Miniature allocation: floor=4, CC quota 2, IMP quota 2.
MINI_ALLOC = {
    "schema_version": 1,
    "floor_units": 4,
    "buckets": [
        {
            "bucket": "B01",
            "prefix": "CC",
            "quota_units": 2,
            "name": "fixture-cc",
            "slice_globs": ["CC-*.json"],
        },
        {
            "bucket": "B07",
            "prefix": "IMP",
            "quota_units": 2,
            "name": "fixture-imp",
            "slice_globs": ["IMP-*.json"],
        },
    ],
}


def _unit(uid: str, **extra: object) -> dict:
    u = deepcopy(MINIMAL_UNIT)
    u["id"] = uid
    u["output_path"] = f"command-center/receipts/{uid}.json"
    u["completion_sentinel"] = f"SUCCESS:{uid}"
    u.update(extra)
    return u


def _write_slice(path: Path, units: list[dict]) -> None:
    path.write_text(json.dumps(units, indent=2) + "\n", encoding="utf-8")


def _clean_slices(tmp_path: Path) -> Path:
    slices = tmp_path / "slices"
    slices.mkdir()
    _write_slice(slices / "CC-1.json", [_unit("CC-0001"), _unit("CC-0002")])
    _write_slice(slices / "IMP-1.json", [_unit("IMP-0001"), _unit("IMP-0002")])
    return slices


def test_planted_duplicate_must_block_merge(tmp_path: Path) -> None:
    slices = tmp_path / "dup"
    slices.mkdir()
    _write_slice(slices / "a.json", [_unit("CC-0001"), _unit("CC-0002")])
    _write_slice(
        slices / "b.json",
        [_unit("CC-0001"), _unit("IMP-0001"), _unit("IMP-0002")],
    )
    with pytest.raises(m.CollisionError) as ei:
        m.assert_merge_contiguous(
            slices, allocation=MINI_ALLOC, require_field_complete=True
        )
    assert "CC-0001" in str(ei.value)
    report = m.build_merge_report(slices, allocation=MINI_ALLOC)
    assert report["inventory"]["duplicate_count"] >= 1
    assert "CC-0001" in report["inventory"]["duplicates"]
    assert report["merge_allowed"] is False
    assert "duplicate-unit-id" in report["block_reasons"]


def test_planted_gap_must_block_merge(tmp_path: Path) -> None:
    slices = tmp_path / "gap"
    slices.mkdir()
    # Missing IMP-0002 → gap inside quota 1..2; also count 3 ≠ floor 4.
    _write_slice(slices / "CC-1.json", [_unit("CC-0001"), _unit("CC-0002")])
    _write_slice(slices / "IMP-1.json", [_unit("IMP-0001")])
    with pytest.raises(m.ContiguityError) as ei:
        m.assert_merge_contiguous(
            slices, allocation=MINI_ALLOC, require_field_complete=True
        )
    msg = str(ei.value)
    assert "gaps=" in msg
    report = m.build_merge_report(slices, allocation=MINI_ALLOC)
    assert report["contiguity"]["total_gap_count"] >= 1
    imp_row = next(
        r for r in report["contiguity"]["per_prefix"] if r["prefix"] == "IMP"
    )
    assert 2 in imp_row["gaps"]
    assert report["merge_allowed"] is False
    assert "index-gap" in report["block_reasons"]
    assert report["exact_question"]["answer"] is False


def test_clean_slice_set_must_merge_positive_control(tmp_path: Path) -> None:
    slices = _clean_slices(tmp_path)
    report = m.assert_merge_contiguous(
        slices, allocation=MINI_ALLOC, require_field_complete=True
    )
    assert report["exact_question"]["answer"] is True
    assert report["merge_allowed"] is True
    assert report["block_reasons"] == []
    assert report["contiguity"]["unique_id_count"] == 4
    assert report["contiguity"]["declared_program_count"] == 4

    catalog = {
        "schema_version": 2,
        "items": [],
        "work_units": [],
        "work_units_meta": {},
    }
    cat_path = tmp_path / "catalog.json"
    cat_path.write_text(json.dumps(catalog) + "\n", encoding="utf-8")
    merged = m.merge_slices(
        slices,
        cat_path,
        write=True,
        allocation=MINI_ALLOC,
        require_contiguous=True,
    )
    assert len(merged["work_units"]) == 4
    assert merged["work_units_meta"]["work_unit_count"] == 4
    assert all(len(v) == 1 for v in m.scan_slice_id_inventory(slices)["sources_by_id"].values())


def test_clean_merge_via_assert_and_report_fields(tmp_path: Path) -> None:
    slices = _clean_slices(tmp_path)
    report = m.build_merge_report(
        slices, allocation=MINI_ALLOC, require_field_complete=True
    )
    assert report["exact_question"]["contiguous"] is True
    assert report["exact_question"]["unique"] is True
    assert report["exact_question"]["exactly_equal_to_declared"] is True
    assert report["field_completeness"]["ok"] is True
    for row in report["inventory"]["per_slice"]:
        assert row["count"] > 0
        assert row["unique_count"] == row["count"]


def test_live_slices_honestly_fail_contiguous_gate() -> None:
    """Live tree is count=2007 shortfall=41 — contiguous gate must refuse."""
    report = m.build_merge_report(m.DEFAULT_SLICES, require_field_complete=False)
    assert report["contiguity"]["unique_id_count"] == 2007
    assert report["contiguity"]["declared_program_count"] == 2048
    assert report["contiguity"]["total_gap_count"] > 0
    assert report["exact_question"]["answer"] is False
    assert report["merge_allowed"] is False
    assert "index-gap" in report["block_reasons"]
    assert "count-claimed-not-read" in report["block_reasons"]
    with pytest.raises(m.ContiguityError):
        m.assert_merge_contiguous(
            m.DEFAULT_SLICES, require_field_complete=False
        )
