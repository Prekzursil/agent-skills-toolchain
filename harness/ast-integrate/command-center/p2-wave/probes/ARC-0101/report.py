#!/usr/bin/env python3
"""Assemble the measured ARC-0101 payload (no artifact I/O)."""
from __future__ import annotations

from typing import Any

import consumers as C
import detector as D

QUESTION = (
    "Do any two keys in any contract schema differ only by case, and does any "
    "consumer parse JSON case-insensitively? The seeded failure class is a "
    "case-insensitive parser colliding on case-distinct keys. Enumerate every "
    "key across all schemas, detect case-collisions mechanically, and test each "
    "consumer's behaviour on a document containing duplicate and case-variant keys."
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0101/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0101/probe2_consumer_table.py"
)


def fingerprint(control: dict[str, Any], census: dict[str, Any], table: list[dict[str, Any]]) -> dict[str, Any]:
    live_rows = [r for r in table if r.get("role") == "live-consumer" and r.get("available")]
    dup_behaviours = sorted(
        {
            str(r.get("duplicate_key", {}).get("behaviour"))
            for r in live_rows
        }
    )
    case_behaviours = sorted(
        {
            str(r.get("case_variant", {}).get("behaviour"))
            for r in live_rows
        }
    )
    seeded = next((r for r in table if r.get("role") == "seeded-failure-class-control"), None)
    strict = next((r for r in table if r.get("role") == "strict-duplicate-control"), None)
    return {
        "detector_control_fired": bool(control.get("fired")),
        "detector_control_clean_silent": bool(control.get("clean_silent")),
        "same_object_case_collision_count": int(census.get("same_object_case_collision_count") or 0),
        "exact_duplicate_count": int(census.get("exact_duplicate_count") or 0),
        "files_parsed": int(census.get("files_parsed") or 0),
        "named_contracts_present": sum(1 for r in D.named_contract_rows() if r["present"]),
        "live_duplicate_behaviours": dup_behaviours,
        "live_case_behaviours": case_behaviours,
        "any_live_consumer_case_insensitive": C.live_case_insensitive(table),
        "seeded_casefold_collapses": bool(
            seeded
            and seeded.get("case_variant", {}).get("behaviour") == "casefold-collapse"
        ),
        "strict_duplicate_errors": bool(
            strict and strict.get("duplicate_key", {}).get("behaviour") == "error"
        ),
    }


def artifact_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain measurements live under report when the receipt_core wrapper is used."""
    if not isinstance(doc, dict):
        return {}
    rep = doc.get("report")
    if isinstance(rep, dict) and (
        "fingerprint" in rep or "detector_control" in rep or "consumers" in rep
    ):
        return rep
    return doc


def measured() -> dict[str, Any]:
    control = D.run_control()
    if not control.get("fired") or not control.get("clean_silent"):
        raise RuntimeError(
            "detector control failed; refusing to trust a schema-key census "
            f"fired={control.get('fired')} clean_silent={control.get('clean_silent')}"
        )
    census = D.census_live()
    table = C.measure_all()
    contracts = D.named_contract_rows()
    fp = fingerprint(control, census, table)
    named_set = set(D.NAMED_CONTRACTS)
    named_collisions = [
        row
        for row in (census.get("same_object_case_collisions") or [])
        if row.get("file") in named_set
    ]
    answers = {
        "named_contract_case_collisions": {
            "count": len(named_collisions),
            "named_contracts_present": fp["named_contracts_present"],
            "named_contracts_expected": len(D.NAMED_CONTRACTS),
            "note": (
                "Named phase-4 contract files ARC-0078..ARC-0087 are absent; "
                "key enumeration still ran over live command-center JSON Schema "
                "files. A zero-collision result is trusted only because the "
                "planted Name/name control fired first."
                if fp["named_contracts_present"] == 0
                else "Named contract files were parsed as schema documents."
            ),
        },
        "live_schema_same_object_case_collisions": fp["same_object_case_collision_count"],
        "any_live_consumer_case_insensitive": fp["any_live_consumer_case_insensitive"],
        "seeded_casefold_hook_collides": fp["seeded_casefold_collapses"],
        "duplicate_key_measured_not_assumed": True,
        "zero_collision_trusted": bool(control.get("trusted"))
        and fp["same_object_case_collision_count"] == 0,
    }
    return {
        "detector_control": control,
        "named_contracts": contracts,
        "schema_census": census,
        "consumers": table,
        "answers": answers,
        "fingerprint": fp,
        "question": QUESTION,
        "probe_commands": {"probe1": P1, "probe2": P2},
    }
