#!/usr/bin/env python3
"""Hand-built fixtures for CNF-0129 mutations and both-states control."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ZERO = "0" * 64
ONE = "1" * 64

SOURCE = {
    "tool": "python3",
    "engine": "jsonschema.Draft7Validator",
    "field": "schema-validation",
}
VERIFIER = {
    "tool": "claim_gate.py",
    "shell": "bash",
    "field": "gate-exit-code",
}


def _repro(command: str, exit_code: int, output: str) -> dict[str, Any]:
    return {"command": command, "exit_code": exit_code, "output": output}


def well_formed_record(**overrides: Any) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "kind": "confirmation-record",
        "claim_id": "CNF-0129-C1",
        "confirmer": {
            "identity": "cnf-0129-reference-confirmer",
            "vendor": "anthropic",
            "role": "confirmation-architect",
        },
        "blinding_attestation_hash": hashlib.sha256(
            b"cnf-0129-dispatched-bytes-allowlist-v1"
        ).hexdigest(),
        "baseline_repro": _repro(
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0129/pre_fix_claim_gate.py command-center/p2-wave/probes/CNF-0129/fixtures/claim-unsourced-confirmed.json",
            0,
            "ok true (pre-fix hole)",
        ),
        "corrected_repro": _repro(
            "PYTHONDONTWRITEBYTECODE=1 python3 -B .agents/skills/claim-verify-gate/scripts/claim_gate.py command-center/p2-wave/probes/CNF-0129/fixtures/claim-unsourced-confirmed.json",
            1,
            "no-source-probe",
        ),
        "rollback_repro": _repro(
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0129/pre_fix_claim_gate.py command-center/p2-wave/probes/CNF-0129/fixtures/claim-unsourced-confirmed.json",
            0,
            "rollback still exhibits the hole",
        ),
        "regression_diff": {
            "path": ".agents/skills/claim-verify-gate/scripts/claim_gate.py",
            "before_sha256": ZERO,
            "after_sha256": ONE,
            "unified_diff": "pre-fix: no no-source-probe. live: no-source-probe fires.",
        },
        "discrepancies": [],
        "verdict": "CONFIRMED",
        "source_probe": copy.deepcopy(SOURCE),
        "verifier_probe": copy.deepcopy(VERIFIER),
        "residual_caveat": (
            "Live claim_gate.py was absent on this worktree before this unit; "
            "BEFORE uses a reconstructed pre-fix fixture named from the catalog hole."
        ),
    }
    rec.update(overrides)
    return rec


def unsourced_confirmed_record() -> dict[str, Any]:
    rec = well_formed_record()
    rec.pop("source_probe", None)
    rec["claim_id"] = "CNF-0129-MUTANT-UNSOURCED"
    rec["verdict"] = "CONFIRMED"
    return rec


def empty_source_confirmed_record() -> dict[str, Any]:
    rec = well_formed_record()
    rec["source_probe"] = ""
    rec["claim_id"] = "CNF-0129-MUTANT-EMPTY-SOURCE"
    return rec


def same_probe_record() -> dict[str, Any]:
    rec = well_formed_record()
    rec["verifier_probe"] = copy.deepcopy(rec["source_probe"])
    rec["claim_id"] = "CNF-0129-MUTANT-SAME-PROBE"
    return rec


def unsourced_confirmed_claim() -> dict[str, Any]:
    return {
        "subject": "CNF-0129 hand-built CONFIRMED with no source_probe",
        "claims": [
            {
                "id": "CNF-0129-C-UNSOURCED",
                "text": "An unsourced CONFIRMED verdict is currently representable.",
                "verdict": "CONFIRMED",
                "evidence": [
                    "command-center/WORK-UNIT-CATALOG.json:31277"
                ],
                "verify_probe": copy.deepcopy(VERIFIER),
            }
        ],
    }


def well_formed_claim() -> dict[str, Any]:
    return {
        "subject": "CNF-0129 both-states well-formed pair",
        "claims": [
            {
                "id": "CNF-0129-C-OK",
                "text": "A well-formed record with two distinct probes validates.",
                "verdict": "CONFIRMED",
                "evidence": ["command-center/schema/confirmation-record.schema.json"],
                "source_probe": copy.deepcopy(SOURCE),
                "verifier_probe": copy.deepcopy(VERIFIER),
            }
        ],
    }


def same_probe_claim() -> dict[str, Any]:
    return {
        "subject": "CNF-0129 same-probe-rerun mutant",
        "claims": [
            {
                "id": "CNF-0129-C-SAME",
                "text": "Byte-identical source and verifier fingerprints are one signal.",
                "verdict": "CONFIRMED",
                "source_probe": copy.deepcopy(SOURCE),
                "verifier_probe": copy.deepcopy(SOURCE),
            }
        ],
    }


def write_fixtures(dirpath: Path) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    mapping = {
        "record-well-formed.json": well_formed_record(),
        "record-unsourced-confirmed.json": unsourced_confirmed_record(),
        "record-empty-source-confirmed.json": empty_source_confirmed_record(),
        "record-same-probe.json": same_probe_record(),
        "claim-unsourced-confirmed.json": unsourced_confirmed_claim(),
        "claim-well-formed.json": well_formed_claim(),
        "claim-same-probe.json": same_probe_claim(),
    }
    for name, doc in mapping.items():
        (dirpath / name).write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
