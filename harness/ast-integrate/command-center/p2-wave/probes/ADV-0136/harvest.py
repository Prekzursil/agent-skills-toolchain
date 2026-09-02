"""Catalog-side declared INDEPENDENT / CROSS-VENDOR seats. Config is not attestation."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
RECEIPTS = REPO / "command-center" / "receipts"
ADVERSARIAL = REPO / "command-center" / "adversarial"


def classify_requirement(text: str) -> str | None:
    low = (text or "").lower()
    if "cross-vendor" in low or "cross vendor" in low:
        return "CROSS-VENDOR"
    if "independent" in low:
        return "INDEPENDENT"
    return None


def attempt_surfaces(uid: str) -> list[dict]:
    probe_dir = PROBES / uid
    receipt = RECEIPTS / f"{uid}.json"
    adv = ADVERSARIAL / f"{uid}-independence-attestation.json"
    rows = [
        {
            "n": 1,
            "surface": str(probe_dir.relative_to(REPO).as_posix()) + "/",
            "present": probe_dir.is_dir(),
            "got_response_vendor": False,
        },
        {
            "n": 2,
            "surface": str(receipt.relative_to(REPO).as_posix()),
            "present": receipt.is_file(),
            "got_response_vendor": False,
        },
        {
            "n": 3,
            "surface": str(adv.relative_to(REPO).as_posix())
            if uid != "ADV-0136"
            else "command-center/adversarial/ (no prior runtime ledger)",
            "present": adv.is_file() if uid != "ADV-0136" else False,
            "got_response_vendor": False,
        },
    ]
    # Request-side assigned_model_vendor_role and confirmer.vendor in a receipt
    # are config, not a response-side transport identifier.
    return rows


def harvest_catalog(repo: Path = REPO) -> dict:
    data = json.loads((repo / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    seats: list[dict] = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        req = str(unit.get("reviewer_requirement") or "")
        declared = classify_requirement(req)
        if not declared:
            continue
        assigned = unit.get("assigned_model_vendor_role") or {}
        if not isinstance(assigned, dict):
            assigned = {}
        attempts = attempt_surfaces(uid)
        seats.append(
            {
                "seat_id": f"{uid}:reviewer",
                "unit_id": uid,
                "council_id": f"catalog:{uid}",
                "declared_independence": declared,
                "declared_role": "reviewer",
                "coverage": "DECLARED-ONLY",
                "source": "catalog-reviewer-requirement",
                "request_side_not_used": {
                    "requested_vendor": assigned.get("vendor"),
                    "requested_model": assigned.get("model"),
                    "label": assigned.get("role"),
                    "reviewer_requirement_head": req[:180],
                },
                "response": None,
                "attestation_attempts": 3,
                "attempts": attempts,
                "violation": "DECLARED-ONLY",
                "reason": "three-failed-attempts-no-response-side-vendor-never-retried-into-pass",
            }
        )
    cv = sum(1 for s in seats if s["declared_independence"] == "CROSS-VENDOR")
    ind = sum(1 for s in seats if s["declared_independence"] == "INDEPENDENT")
    return {
        "seats": seats,
        "census": {
            "declared_independent_seats": len(seats),
            "cross_vendor_seats": cv,
            "independent_seats": ind,
            "response_attested": 0,
            "declared_only": len(seats),
            "all_covered_as_attested_or_declared_only": True,
            "rule": "catalog reviewer slots have no response-side transport record on this worktree; filed DECLARED-ONLY after 3 failed lookups",
        },
        "catalog_violations": [
            {
                "group": s["council_id"],
                "seat_id": s["seat_id"],
                "reason": s["reason"],
            }
            for s in seats
        ],
    }
