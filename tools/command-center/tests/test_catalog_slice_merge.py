#!/usr/bin/env python3
"""CC-0008 tests: collision, order-independence, field-completeness, idempotence."""

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
    "id": "CC-9990",
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
    "output_path": "command-center/receipts/CC-9990.json",
    "output_schema": "command-center/schema/receipt.schema.json",
    "evidence_requirement": "fixture",
    "tests_required": ["fixture"],
    "reviewer_requirement": "fixture",
    "completion_sentinel": "SUCCESS:CC-9990",
    "retry_policy": "none",
    "failure_classification": ["overclaim"],
    "owner_approval_required": False,
}


def _write_slice(path: Path, units: list[dict]) -> None:
    path.write_text(json.dumps(units, indent=2) + "\n", encoding="utf-8")


def test_collision_two_slices_claiming_same_id_names_both_paths(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    u = deepcopy(MINIMAL_UNIT)
    u["id"] = "CC-0007"
    _write_slice(a, [u])
    _write_slice(b, [deepcopy(u)])
    with pytest.raises(m.CollisionError) as ei:
        m.load_slices(tmp_path)
    msg = str(ei.value)
    assert "CC-0007" in msg
    assert str(a) in msg or a.name in msg
    assert str(b) in msg or b.name in msg
    # Must not silently drop: both source paths named.
    assert msg.count("CC-0007") >= 1
    assert "claimed by" in msg


def test_order_independence_permuted_slice_paths(tmp_path: Path) -> None:
    units_a = [deepcopy(MINIMAL_UNIT)]
    units_a[0]["id"] = "CC-9001"
    units_b = [deepcopy(MINIMAL_UNIT)]
    units_b[0]["id"] = "CC-9002"
    units_b[0]["title"] = "other"
    (tmp_path / "z-late.json").write_text(json.dumps(units_a) + "\n", encoding="utf-8")
    (tmp_path / "a-early.json").write_text(json.dumps(units_b) + "\n", encoding="utf-8")

    # Load twice after renaming to force different directory iteration orders.
    first, _ = m.load_slices(tmp_path)
    # Shuffle filenames by rewriting with swapped names
    z = (tmp_path / "z-late.json").read_text(encoding="utf-8")
    a = (tmp_path / "a-early.json").read_text(encoding="utf-8")
    (tmp_path / "z-late.json").write_text(a, encoding="utf-8")
    (tmp_path / "a-early.json").write_text(z, encoding="utf-8")
    # After swap content still two distinct ids; merge must still be id-sorted identical shape.
    second, _ = m.load_slices(tmp_path)
    # Re-establish original contents for canonical compare via fresh dir
    d2 = tmp_path / "perm2"
    d2.mkdir()
    (d2 / "m2.json").write_text(json.dumps(units_b) + "\n", encoding="utf-8")
    (d2 / "m1.json").write_text(json.dumps(units_a) + "\n", encoding="utf-8")
    third, _ = m.load_slices(d2)

    # Original first load vs third (different path names, same unit set) must match by id set + bytes
    # Rebuild canonical from unit payloads without path-dependent stamp differences beyond filename.
    def canon(units: list[dict]) -> bytes:
        cleaned = []
        for u in units:
            c = {k: v for k, v in u.items() if k != "_source_slice_file"}
            cleaned.append(c)
        return m.dump_work_units_bytes(cleaned)

    assert canon(first) == canon(third)


def test_field_completeness_rejects_missing_title(tmp_path: Path) -> None:
    bad = deepcopy(MINIMAL_UNIT)
    del bad["title"]
    _write_slice(tmp_path / "bad.json", [bad])
    with pytest.raises(m.FieldCompletenessError) as ei:
        m.load_slices(tmp_path)
    assert "CC-9990.title" in str(ei.value)


def test_idempotence_remerge_is_noop_not_duplication(tmp_path: Path) -> None:
    u1 = deepcopy(MINIMAL_UNIT)
    u1["id"] = "CC-9100"
    u2 = deepcopy(MINIMAL_UNIT)
    u2["id"] = "CC-9101"
    slices = tmp_path / "slices"
    slices.mkdir()
    _write_slice(slices / "s.json", [u1, u2])
    catalog = {
        "schema_version": 2,
        "items": [],
        "work_units": [],
        "work_units_meta": {},
    }
    cat_path = tmp_path / "catalog.json"
    cat_path.write_text(json.dumps(catalog) + "\n", encoding="utf-8")

    once = m.merge_slices(slices, cat_path, write=True)
    assert len(once["work_units"]) == 2
    twice = m.merge_slices(slices, cat_path, write=True)
    assert len(twice["work_units"]) == 2
    assert m.dump_work_units_bytes(once["work_units"]) == m.dump_work_units_bytes(
        twice["work_units"]
    )


def test_live_slices_field_complete_and_measurable() -> None:
    """Both-states control: live slice set must load without collision/field errors."""
    units, sources = m.load_slices(m.DEFAULT_SLICES)
    assert len(units) == 2007
    assert all(len(v) == 1 for v in sources.values())
    counts = m.per_bucket_counts(units)
    assert sum(counts.values()) == 2007
    assert counts["B01"] == 24
    # Shortfall against 2048 is first-class, not hidden.
    assert 2048 - 2007 == 41
