"""Fixture trees for CNF-0140 detector controls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _attestation(claim_id: str) -> str:
    return hashlib.sha256(f"blind:{claim_id}".encode("utf-8")).hexdigest()


def confirmation_record(claim_id: str, record_id: str, verdict: str = "CONFIRMED") -> dict[str, Any]:
    return {
        "id": record_id,
        "claim_id": claim_id,
        "confirmer": {"id": "cnf-0140-fixture-confirmer", "vendor": "openai"},
        "verdict": verdict,
        "source_probe": f"source:{claim_id}",
        "verifier_probe": f"verifier:{claim_id}",
        "blinding_attestation": _attestation(claim_id),
        "baseline_repro": "fixture-baseline",
        "corrected_repro": "fixture-corrected",
        "rollback_repro": "fixture-rollback",
        "regression_diff": "",
        "discrepancies": [],
        "residual_caveat": "",
    }


def registry_doc() -> dict[str, Any]:
    claims = [
        {"id": "CLAIM-P0-PRESENT", "severity": "P0", "text": "Known-present P0 with a record."},
        {"id": "CLAIM-P0-DELETED", "severity": "P0", "text": "Known P0 whose record was deleted."},
        {"id": "CLAIM-P1-PRESENT", "severity": "P1", "text": "Known-present P1 with a record."},
        {"id": "CLAIM-P0-EXTRA", "severity": "P0", "text": "Second P0 with a record."},
        {"id": "CLAIM-P1-EXTRA", "severity": "P1", "text": "Second P1 with a record."},
        {"id": "CLAIM-P2-LOW", "severity": "P2", "text": "Lower severity; sampling-eligible."},
        {
            "id": "CLAIM-P2-UNDER",
            "severity": "P2",
            "text": "Author-graded P2; CNF-0142 re-grades to P1.",
        },
        {"id": "CLAIM-UNGRADED", "text": "Missing severity; must not default to low."},
    ]
    return {"schema_version": 1, "claims": claims}


RECORDS = {
    "CLAIM-P0-PRESENT": "B09-REC-CLAIM-P0-PRESENT",
    "CLAIM-P1-PRESENT": "B09-REC-CLAIM-P1-PRESENT",
    "CLAIM-P0-EXTRA": "B09-REC-CLAIM-P0-EXTRA",
    "CLAIM-P1-EXTRA": "B09-REC-CLAIM-P1-EXTRA",
}


def write_known_present(root: Path | None = None) -> Path:
    root = root or (FIX / "known-present")
    _write(root / "CLAIM-REGISTRY.json", registry_doc())
    rec_dir = root / "records"
    if rec_dir.exists():
        for child in rec_dir.iterdir():
            if child.is_file():
                child.unlink()
    rec_dir.mkdir(parents=True, exist_ok=True)
    for claim_id, record_id in RECORDS.items():
        _write(rec_dir / f"{record_id}.json", confirmation_record(claim_id, record_id))
    # Unparseable leftover must not count as a confirmation for CLAIM-P0-DELETED.
    (rec_dir / "B09-REC-ORPHAN-GARBAGE.json").write_text("{not-json", encoding="utf-8")
    return root


def write_empty_records(root: Path | None = None) -> Path:
    root = root or (FIX / "empty-records")
    _write(root / "CLAIM-REGISTRY.json", registry_doc())
    rec_dir = root / "records"
    rec_dir.mkdir(parents=True, exist_ok=True)
    for child in rec_dir.iterdir():
        if child.is_file():
            child.unlink()
    return root


def write_empty_population(root: Path | None = None) -> Path:
    root = root or (FIX / "empty-population")
    _write(root / "CLAIM-REGISTRY.json", {"schema_version": 1, "claims": []})
    rec_dir = root / "records"
    rec_dir.mkdir(parents=True, exist_ok=True)
    for child in rec_dir.iterdir():
        if child.is_file():
            child.unlink()
    return root


def write_regrade_overlay(root: Path | None = None) -> Path:
    root = root or (FIX / "regrade")
    write_known_present(root)
    _write(
        root / "CNF-0142.json",
        {
            "unit_id": "CNF-0142",
            "under_grades": [
                {
                    "claim_id": "CLAIM-P2-UNDER",
                    "original_severity": "P2",
                    "revised_severity": "P1",
                    "direction": "under-grade",
                    "rubric_clause": "CNF-0140 severity-coupling fixture",
                }
            ],
        },
    )
    return root


def materialize() -> dict[str, Path]:
    return {
        "known_present": write_known_present(),
        "empty_records": write_empty_records(),
        "empty_population": write_empty_population(),
        "regrade": write_regrade_overlay(),
    }
