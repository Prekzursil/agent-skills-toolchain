"""Council risk-class routing to protocol and quorum floors. IMP-0358.

A declared risk class maps onto minimum protocol strength, quorum, evidence
standard and reviewer count. The class is bound when deliberation starts and is
immutable for the life of the session: a mid-run reclassification is refused
with event RISK_CLASS_MUTATION_REFUSED. Floors are monotone across classes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RISK_CLASSES = ("LOW", "MODERATE", "HIGH", "CRITICAL")
RISK_CLASS_RANK = {name: i for i, name in enumerate(RISK_CLASSES)}

EVENT_MUTATION_REFUSED = "EVENT_MUTATION_REFUSED"
EVENT_RISK_CLASS_MUTATION_REFUSED = "RISK_CLASS_MUTATION_REFUSED"
EVENT_START_WITHOUT_CLASS = "EVENT_START_WITHOUT_CLASS"

EVIDENCE_TIERS = ("any-cited", "peer-reviewed-only", "executable-proof-only")
EVIDENCE_TIER_RANK = {name: i for i, name in enumerate(EVIDENCE_TIERS)}

FLOORS = {
    "LOW": {
        "protocol_strength": 1, "quorum": 2,
        "evidence_standard": "any-cited", "reviewer_count": 1,
    },
    "MODERATE": {
        "protocol_strength": 2, "quorum": 3,
        "evidence_standard": "peer-reviewed-only", "reviewer_count": 1,
    },
    "HIGH": {
        "protocol_strength": 3, "quorum": 5,
        "evidence_standard": "peer-reviewed-only", "reviewer_count": 2,
    },
    "CRITICAL": {
        "protocol_strength": 4, "quorum": 5,
        "evidence_standard": "executable-proof-only", "reviewer_count": 3,
    },
}


class RiskError(ValueError):
    pass
