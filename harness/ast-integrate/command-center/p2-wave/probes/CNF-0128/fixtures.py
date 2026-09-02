#!/usr/bin/env python3
"""Green Phase 11 corpus and named mutants for both-states controls."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

THRESHOLD = 0.10

P0P1 = (
    ("C-P0-ALPHA", "P0", "The sampling frame includes every P0 claim."),
    ("C-P0-BETA", "P1", "The escalation threshold was fixed before confirmations."),
    ("C-P1-GAMMA", "P1", "Coverage board numbers come from receipts on disk."),
)


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def claim_receipt(claim_id: str, severity: str, text: str) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "severity": severity,
        "text": text,
        "verdict": "CONFIRMED",
        "confirmer_id": f"confirmer-{claim_id}-a",
        "confirmer_vendor": "openai",
        "source_probe": f"sha256:source-{claim_id}-probe-one",
        "verifier_probe": f"sha256:verifier-{claim_id}-probe-two",
        "source_probe_output": f"PASS {claim_id} source",
        "verifier_probe_output": f"PASS {claim_id} verifier",
        "residual": None,
    }


def policy(*, open_escalations: list | None = None, threshold: float = THRESHOLD) -> dict:
    open_escalations = list(open_escalations or [])
    return {
        "unit_id": "CNF-0004",
        "state": "SUCCESS",
        "discrepancy_rate_threshold": threshold,
        "threshold_fixed_before_confirmations": True,
        "committed_at": "2026-01-01T00:00:00Z",
        "class_wide_escalation_open": bool(open_escalations),
        "open_escalations": open_escalations,
    }


def sample(*, n: int = 10, disagreements: int = 0) -> dict:
    items = []
    for i in range(n):
        items.append(
            {
                "id": f"S{i:02d}",
                "disagreement": i < disagreements,
                "source_probe": f"sha256:sample-src-{i}",
                "verifier_probe": f"sha256:sample-ver-{i}",
            }
        )
    return {
        "unit_id": "CNF-0118",
        "state": "SUCCESS",
        "sample_size": n,
        "disagreements": disagreements,
        "error_rate": (disagreements / n) if n else None,
        "items": items,
    }


def audit(unit_id: str, kind: str) -> dict:
    return {
        "unit_id": unit_id,
        "state": "SUCCESS",
        "audit_kind": kind,
        "blocks_phase11_exit": False,
        "findings": [],
    }


def coverage_board() -> dict:
    return {
        "unit_id": "CNF-0014",
        "state": "SUCCESS",
        "generated_from_receipts": True,
        "counts": {
            "P0": 1,
            "P1": 2,
            "confirmed": 3,
            "refuted": 0,
            "partial": 0,
            "not_checked": 0,
            "blocked": 0,
            "stale": 0,
        },
    }


def write_registry(root: Path, claims: list[tuple[str, str, str]] | None = None) -> None:
    claims = list(claims if claims is not None else P0P1)
    dump(
        root / "command-center/CLAIM-REGISTRY.json",
        {
            "verdict_vocabulary": [
                "CONFIRMED",
                "REFUTED",
                "PARTIAL",
                "NOT-CHECKED",
                "BLOCKED",
            ],
            "claims": [
                {
                    "id": cid,
                    "severity": sev,
                    "text": text,
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": (
                        "Run the named confirmation probes for this claim."
                    ),
                }
                for cid, sev, text in claims
            ],
        },
    )


def write_required(root: Path, *, open_escalations=None, n=10, disagreements=0) -> None:
    dump(
        root / "command-center/confirmation/CNF-0004-escalation-policy.json",
        policy(open_escalations=open_escalations),
    )
    dump(
        root / "command-center/confirmation/CNF-0014-coverage-board.json",
        coverage_board(),
    )
    dump(
        root / "command-center/confirmation/CNF-0118-second-order-sample.json",
        sample(n=n, disagreements=disagreements),
    )
    dump(
        root / "command-center/confirmation/CNF-0120-not-checked-integrity.json",
        audit("CNF-0120", "not-checked-integrity"),
    )
    dump(
        root / "command-center/confirmation/CNF-0124-authorship-audit.json",
        audit("CNF-0124", "authorship-audit"),
    )
    dump(
        root / "command-center/confirmation/CNF-0125-stale-premise-sweep.json",
        audit("CNF-0125", "stale-premise-sweep"),
    )


def write_claim_receipts(root: Path) -> Path:
    last = root
    for cid, sev, text in P0P1:
        rec = claim_receipt(cid, sev, text)
        if cid == "C-P1-GAMMA":
            rec["residual"] = {
                "id": "R-DISCLOSED-COVERAGE-STAMP",
                "statement": (
                    "Coverage board commit stamp is disclosed as a residual "
                    "until the live tree has a git commit producing it."
                ),
                "settling_experiment": (
                    "Once CNF-0014 exists on the live tree, re-hash the board "
                    "against HEAD and require byte identity with the generator."
                ),
            }
        path = root / f"command-center/confirmation/receipts/{cid}.json"
        dump(path, rec)
        last = path
    return last


def build_green(root: Path) -> Path:
    write_registry(root)
    write_required(root)
    write_claim_receipts(root)
    return root


REMOVED_RECEIPT = "command-center/confirmation/receipts/C-P0-ALPHA.json"


def mutate_remove_one_receipt(root: Path) -> str:
    path = root / REMOVED_RECEIPT
    path.unlink()
    return REMOVED_RECEIPT


def mutate_open_escalation(root: Path) -> None:
    dump(
        root / "command-center/confirmation/CNF-0004-escalation-policy.json",
        policy(
            open_escalations=[
                {
                    "stratum": "P0",
                    "reason": "planted class-wide re-queue",
                    "expansion_count": 12,
                }
            ]
        ),
    )


def mutate_high_error_rate(root: Path) -> None:
    dump(
        root / "command-center/confirmation/CNF-0118-second-order-sample.json",
        sample(n=10, disagreements=3),
    )
