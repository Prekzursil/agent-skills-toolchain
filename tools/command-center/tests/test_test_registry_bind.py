#!/usr/bin/env python3
"""CC-0014 tests: UNPROVEN / PROTECTING / HOLE / aggregation controls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import test_registry_bind as trb  # noqa: E402


def _base_entry(**overrides):
    e = {
        "id": "BIND-001",
        "test_id": "test_example_can_go_red",
        "claim_ids": ["CC-2"],
        "unit_ids": ["CC-0014"],
        "mutation_record": None,
    }
    e.update(overrides)
    return e


def test_no_mutation_is_unproven_and_not_coverage() -> None:
    entry = trb.normalize_entry(_base_entry())
    assert entry["status"] == trb.STATUS_UNPROVEN
    reg = {"bindings": [entry]}
    summary = trb.coverage_summary(reg)
    assert summary["by_status"][trb.STATUS_UNPROVEN] == 1
    assert summary["protected_claim_count"] == 0
    assert summary["unproven_count_toward_coverage"] == 0


def test_mutation_failed_is_protecting() -> None:
    entry = trb.normalize_entry(
        _base_entry(
            mutation_record={
                "outcome": "FAILED",
                "diff_ref": "command-center/p2-wave/probes/CC-0014/fixtures/mut.diff",
                "failing_output_ref": (
                    "command-center/p2-wave/probes/CC-0014/fixtures/mut-fail.out"
                ),
                "description": "flipped constant; test went red",
            }
        )
    )
    assert entry["status"] == trb.STATUS_PROTECTING
    summary = trb.coverage_summary({"bindings": [entry]})
    assert summary["protected_claim_count"] == 1
    assert summary["protected_claims"] == ["CC-2"]


def test_survived_mutation_is_hole_not_silent_downgrade() -> None:
    entry = trb.normalize_entry(
        _base_entry(
            mutation_record={
                "outcome": "SURVIVED",
                "diff_ref": "fixtures/survived.diff",
                "failing_output_ref": "fixtures/still-green.out",
                "description": "mutant lived; suite stayed green",
            }
        )
    )
    assert entry["status"] == trb.STATUS_HOLE
    summary = trb.coverage_summary({"bindings": [entry]})
    assert summary["hole_count"] == 1
    assert summary["holes"][0]["entry_id"] == "BIND-001"
    assert summary["protected_claim_count"] == 0


def test_aggregation_all_unproven_reports_zero_protected() -> None:
    bindings = [
        trb.normalize_entry(_base_entry(id=f"BIND-{i}", claim_ids=[f"C-{i}"]))
        for i in range(5)
    ]
    summary = trb.coverage_summary({"bindings": bindings})
    assert summary["binding_count"] == 5
    assert summary["by_status"][trb.STATUS_UNPROVEN] == 5
    assert summary["protected_claim_count"] == 0
    assert summary["coverage_ratio"] == 0.0


def test_protecting_requires_evidence_pointers() -> None:
    with pytest.raises(trb.RegistryError):
        trb.normalize_entry(
            _base_entry(mutation_record={"outcome": "FAILED"})  # missing refs
        )


def test_register_entry_roundtrip(tmp_path: Path) -> None:
    reg = trb.ensure_bindings_scaffold({"schema_version": 1, "suites": []})
    path = tmp_path / "reg.json"
    trb.save_registry(reg, path)
    entry = _base_entry(
        mutation_record={
            "outcome": "FAILED",
            "diff_ref": "d",
            "failing_output_ref": "o",
        }
    )
    trb.register_entry(reg, entry)
    trb.save_registry(reg, path)
    loaded = trb.load_registry(path)
    assert loaded["bindings"][0]["status"] == trb.STATUS_PROTECTING
