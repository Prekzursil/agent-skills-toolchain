"""Pre-registered gem-hunt rubric. Scoring lives in score.py.

This module is the published instrument. It must be hashed before any
call-sheet row is scored. Changing a threshold after seeing grades is a
protocol violation, not a calibration update.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BUS_FIT = (
    "RIDES-BUS",
    "RIDES-BUS+STATE",
    "RIDES-BUS+DAEMON",
    "SECOND RUNTIME",
)

EVIDENCE_TIERS = ("E1", "E2", "E3", "E4")

RUBRIC: dict[str, Any] = {
    "id": "RES-0108-gem-hunt-rubric-v1",
    "title": "Operational GEM criteria (leverage, irreplaceability, measured evidence, bus-fit)",
    "protocol": (
        "Publish this document and its sha256 BEFORE loading call-sheet grades. "
        "The scorer may read only the feature card. A perfect match against the "
        "existing Tier-1 labels is suspicious, not reassuring."
    ),
    "axes": {
        "leverage": {
            "id": "L",
            "question": "Leverage per unit of integration cost",
            "scale": "integer 0 (none) .. 3 (high)",
            "pass": "leverage >= 2 AND integration_cost <= 1",
        },
        "irreplaceability": {
            "id": "I",
            "question": "Is the mechanism irreplaceable here, or a rename of something already owned?",
            "pass": "irreplaceable is true AND rename_of_existing is false",
        },
        "measured_evidence": {
            "id": "E",
            "question": "Is there measured evidence with a baseline, or only a headline?",
            "pass": (
                "evidence_tier in {E1, E2} AND has_baseline is true "
                "AND has_effect_size is true"
            ),
            "note": (
                "E3 (single source / no baseline) may not promote a mechanism. "
                "A headline number without its baseline is E3."
            ),
        },
        "bus_fit": {
            "id": "B",
            "question": "Does it ride the existing bus, or demand a second runtime?",
            "vocabulary": list(BUS_FIT),
            "pass": "bus_fit in {RIDES-BUS, RIDES-BUS+STATE}",
            "fail_closed": {
                "RIDES-BUS+DAEMON": "daemon is a liability with a self-healing tax; not a GEM",
                "SECOND RUNTIME": "adopting a mechanism, never a second orchestration runtime",
            },
        },
    },
    "gem_rule": (
        "A mechanism is a GEM if and only if gates L, I, E, and B all pass. "
        "The conjunction is the definition; no axis may be waived after seeing grades."
    ),
    "feature_keys": [
        "leverage",
        "integration_cost",
        "irreplaceable",
        "rename_of_existing",
        "evidence_tier",
        "has_baseline",
        "has_effect_size",
        "bus_fit",
    ],
    "forbidden_scorer_keys": [
        "call_sheet_grade",
        "call_sheet_tier",
        "label",
        "expected_gem",
        "name",
        "reconstruction_confidence",
    ],
}


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def published_sha256(obj: Any | None = None) -> str:
    return hashlib.sha256(canonical_bytes(obj if obj is not None else RUBRIC)).hexdigest()


def dump_published(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(RUBRIC)
    path.write_bytes(raw + b"\n")
    # Hash the published object, not the trailing newline, so a re-read of the
    # JSON value matches the recorded digest.
    return hashlib.sha256(raw).hexdigest()
