"""Known-count fixture claims and receipts for CNF-0014 controls.

These are not the live corpus. Probes write them into a tempfile so the
generator is exercised against receipts on disk, not against literals in
the probe assertion.
"""
from __future__ import annotations

from typing import Any

# Six claims: one of each interesting severity, plus a second P0 and a P3.
CLAIMS: list[dict[str, Any]] = [
    {"claim_id": "CLM-P0-CONFIRMED", "severity": "P0"},
    {"claim_id": "CLM-P0-REFUTED", "severity": "P0"},
    {"claim_id": "CLM-P1-PARTIAL", "severity": "P1"},
    {"claim_id": "CLM-P1-ABSENT", "severity": "P1"},
    {"claim_id": "CLM-P2-BLOCKED", "severity": "P2"},
    {"claim_id": "CLM-P3-STALE", "severity": "P3"},
]


def _receipt(
    claim_id: str,
    verdict: str,
    *,
    hashes: dict[str, str] | None,
    severity: str,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "claim_id": claim_id,
        "severity": severity,
        "confirmer": {"id": "cnf-0014-fixture-confirmer", "role": "confirmer"},
        "source_probe": {
            "id": "source",
            "fingerprint": f"src-{claim_id}",
        },
        "verifier_probe": {
            "id": "verifier",
            "fingerprint": f"ver-{claim_id}",
        },
        "verbatim_output": f"fixture probe output for {claim_id}",
        "verdict": verdict,
        "residual": "fixture residual",
    }
    if hashes is not None:
        rec["input_hashes"] = hashes
    return rec


# Five receipts. CLM-P1-ABSENT has none -> not_checked.
# CLM-P3-STALE is stored CONFIRMED with no input_hashes -> STALE by CNF-0012.
RECEIPTS: list[dict[str, Any]] = [
    _receipt(
        "CLM-P0-CONFIRMED",
        "CONFIRMED",
        hashes={"spec": "a" * 64},
        severity="P0",
    ),
    _receipt(
        "CLM-P0-REFUTED",
        "REFUTED",
        hashes={"spec": "b" * 64},
        severity="P0",
    ),
    _receipt(
        "CLM-P1-PARTIAL",
        "PARTIAL",
        hashes={"spec": "c" * 64},
        severity="P1",
    ),
    _receipt(
        "CLM-P2-BLOCKED",
        "BLOCKED",
        hashes={"spec": "d" * 64},
        severity="P2",
    ),
    _receipt(
        "CLM-P3-STALE",
        "CONFIRMED",
        hashes=None,
        severity="P3",
    ),
]

EXPECTED_TALLIES = {
    "claims_n": 6,
    "measured": 5,
    "confirmed": 1,
    "refuted": 1,
    "partial": 1,
    "not_checked": 1,
    "blocked": 1,
    "stale": 1,
}

FIXTURE_COMMIT = "FIXTURE-COMMIT"
