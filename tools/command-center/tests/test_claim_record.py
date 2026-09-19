#!/usr/bin/env python3
"""CC-0017 planted controls for the provisional claim-record contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import claim_record as cr

REPO = Path(__file__).resolve().parents[3]
REGISTRY = REPO / "command-center/CLAIM-REGISTRY.json"


def _base_record(**overrides):
    rec = {
        "schema_version": 1,
        "schema_status": "PROVISIONAL",
        "superseded_by_unit": "ARC-0085",
        "claim_id": "T-1",
        "canonical_mechanism": "mechanism-alpha",
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [{"anchor": "tests://fixture", "probe": "unit"}],
        "confidence": "likely",
        "verification_status": "UNVERIFIED",
        "implementation_impact": "test-only",
        "settling_probe": "pytest tools/command-center/tests/test_claim_record.py -q",
    }
    rec.update(overrides)
    return rec


def test_missing_settling_probe_is_rejected() -> None:
    rec = _base_record()
    del rec["settling_probe"]
    errs = cr.validate_claim(rec, known_ids={"T-1"}, check_edges=True)
    assert any("settling_probe" in e for e in errs)

    rec2 = _base_record(settling_probe="")
    errs2 = cr.validate_claim(rec2, known_ids={"T-1"}, check_edges=True)
    assert any("settling_probe" in e for e in errs2)


def test_duplicate_of_cycle_is_rejected() -> None:
    a = _base_record(claim_id="A", duplicate_of=["B"], settling_probe="probe-a")
    b = _base_record(claim_id="B", duplicate_of=["A"], settling_probe="probe-b")
    errs = cr.validate_registry([a, b])
    assert any("duplicate_of cycle" in e for e in errs)
    with pytest.raises(cr.ClaimRecordError, match="duplicate_of cycle"):
        cr.assert_valid_registry([a, b])


def test_contradiction_to_nonexistent_claim_id_is_rejected() -> None:
    rec = _base_record(contradicts=["DOES-NOT-EXIST"])
    errs = cr.validate_claim(rec, known_ids={"T-1"}, check_edges=True)
    assert any("DOES-NOT-EXIST" in e and "contradicts" in e for e in errs)

    # Registry-level: only T-1 exists
    errs2 = cr.validate_registry([rec])
    assert any("DOES-NOT-EXIST" in e for e in errs2)


def test_roundtrip_migrate_three_real_registry_records_no_field_loss() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in data["claims"]}
    # Three real rows spanning settling_experiment / verifier / source only.
    selected = ["CC-1", "CC-2", "CC-7"]
    legacy_rows = [by_id[i] for i in selected]

    migrated = [cr.migrate_from_legacy(copy.deepcopy(row)) for row in legacy_rows]
    for legacy, mig in zip(legacy_rows, migrated):
        assert mig["legacy_fields"] == legacy
        assert cr.roundtrip_legacy_fields(legacy) is True
        # Every original key present with identical value
        for key, value in legacy.items():
            assert key in mig["legacy_fields"]
            assert mig["legacy_fields"][key] == value

    errs = cr.validate_registry(migrated)
    assert errs == [], errs


def test_schema_declares_provisional_and_arc0085_superseder() -> None:
    meta = cr.provisional_meta()
    assert meta["provisional"] is True
    assert meta["schema_status"] == "PROVISIONAL"
    assert meta["superseded_by_unit"] == "ARC-0085"
    assert meta["phase4_formalization_unit"] == "ARC-0085"
    schema = cr.load_schema()
    assert schema["x-provisional"] is True
    assert schema["x-superseded-by-unit"] == "ARC-0085"
    assert "PROVISIONAL" in schema["description"]


def test_schedule_recompute_from_edge_list_not_restated() -> None:
    result = cr.recompute_schedule_after_soft_1_2()
    assert result["edge_1_2_flipped_hard_to_soft"] is True
    assert result["before"]["node_count"] == 11
    assert result["after"]["node_count"] == 10
    assert result["b03_units_released_if_soft"] == 224
    assert result["schedule_claim_recomputed"]["units_released"] == 224
    assert result["schedule_claim_recomputed"]["critical_path_before"] == 11
    assert result["schedule_claim_recomputed"]["critical_path_after"] == 10
    assert result["after"]["critical_path"] == [
        "0",
        "1",
        "2A",
        "2B",
        "7",
        "7A",
        "10",
        "11",
        "14",
        "15",
    ]
