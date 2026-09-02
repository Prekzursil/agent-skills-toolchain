#!/usr/bin/env python3
"""Both-states and negative-control fixtures for CNL-0081."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX_DIR = HERE / "fixtures"

ROSTER = {
    "participants": [
        {"id": "p-author", "roles": ["ClaimAuthor"]},
        {"id": "p-critic", "roles": ["CounterexampleAuthor"]},
        {"id": "p-registrar", "roles": ["LoadBearingRegistrar"]},
        {"id": "p-certifier", "roles": ["ResolutionCertifier"]},
        {"id": "p-evidence", "roles": ["EvidenceProducer"]},
        {"id": "p-qg", "roles": ["QualityGateOperator"]},
    ]
}

RESOLVED_OK = {
    "id": "cx-1",
    "claim_id": "claim-1",
    "author_id": "p-critic",
    "declared_load_bearing": True,
    "declared_load_bearing_by": "p-registrar",
    "resolved": True,
    "resolved_by": "p-certifier",
    "evidence_producer_id": "p-evidence",
    "resolving_evidence_ref": "ev-1",
}

OPEN_LB = {
    "id": "cx-open",
    "claim_id": "claim-1",
    "author_id": "p-critic",
    "declared_load_bearing": True,
    "declared_load_bearing_by": "p-registrar",
    "resolved": False,
    "resolved_by": None,
    "evidence_producer_id": None,
    "resolving_evidence_ref": None,
}


def _base(records: list[dict[str, Any]], quality_gate: str, claimed_unresolved: int) -> dict[str, Any]:
    return {
        "round_id": "r-1",
        "quality_gate": quality_gate,
        "quality_gate_operator_id": "p-qg",
        "unresolved_load_bearing_counterexample": claimed_unresolved,
        "counterexamples": deepcopy(records),
        "roster": deepcopy(ROSTER),
    }


def fire_state() -> dict[str, Any]:
    """quality_gate PASS and derived unresolved == 0 (seats all distinct)."""
    st = _base([RESOLVED_OK], "PASS", 0)
    st["fixture_id"] = "FIRE"
    st["expected_decision"] = "FIRE"
    return st


def silent_unresolved_state() -> dict[str, Any]:
    """quality_gate PASS but one load-bearing counterexample still open."""
    st = _base([OPEN_LB], "PASS", 1)
    st["fixture_id"] = "SILENT-unresolved"
    st["expected_decision"] = "SILENT"
    return st


def silent_quality_fail_state() -> dict[str, Any]:
    """Derived unresolved == 0 but quality_gate FAIL — AND stays SILENT."""
    st = _base([RESOLVED_OK], "FAIL", 0)
    st["fixture_id"] = "SILENT-quality-fail"
    st["expected_decision"] = "SILENT"
    return st


def negative_dual_role_state() -> dict[str, Any]:
    """Same participant declares load-bearing AND certifies resolution.

    Claimed unresolved is 0 and quality_gate is PASS. Derived count stays 1
    because seats_ok is false. The check is meant to REJECT this state:
    decision must be SILENT.
    """
    rec = deepcopy(RESOLVED_OK)
    rec["id"] = "cx-dual"
    rec["resolved_by"] = rec["declared_load_bearing_by"]  # p-registrar does both
    st = _base([rec], "PASS", 0)
    st["fixture_id"] = "NEG-dual-role"
    st["expected_decision"] = "SILENT"
    st["negative_control"] = True
    st["rejects"] = "same-participant-declare-and-resolve"
    return st


def negative_claimed_lie_state() -> dict[str, Any]:
    """Claimed unresolved=0 while an open load-bearing record exists."""
    st = _base([OPEN_LB], "PASS", 0)
    st["fixture_id"] = "NEG-claimed-lie"
    st["expected_decision"] = "SILENT"
    st["negative_control"] = True
    st["rejects"] = "claimed-zero-with-open-record"
    return st


def all_fixtures() -> list[dict[str, Any]]:
    return [
        fire_state(),
        silent_unresolved_state(),
        silent_quality_fail_state(),
        negative_dual_role_state(),
        negative_claimed_lie_state(),
    ]


def write_fixture_files() -> list[Path]:
    FIX_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for st in all_fixtures():
        path = FIX_DIR / f"{st['fixture_id']}.json"
        path.write_text(
            json.dumps(st, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths


if __name__ == "__main__":
    for p in write_fixture_files():
        print(p)
