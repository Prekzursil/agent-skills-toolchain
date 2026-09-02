"""Compose a CouncilSpec from inputs. Pure function of question/stakeholders/risk_tier."""
from __future__ import annotations

from typing import Any

SECTIONS = (
    "charter",
    "participants",
    "roles",
    "engagement",
    "budgets",
    "evidence",
    "voting",
    "stopping",
    "outcomes",
    "integrity",
    "artifacts",
    "execution",
    "meta",
)

EXAMPLE = {
    "question": "Should we ship the council runtime?",
    "stakeholders": ["customer", "operator", "reviewer"],
    "risk_tier": "T2",
}


def load_example() -> dict[str, Any]:
    return dict(EXAMPLE)


def compose_council_spec(
    question: str,
    stakeholders: list[str],
    risk_tier: str,
) -> dict[str, Any]:
    people = list(stakeholders)
    spec = {
        "charter": {"question": question, "risk_tier": risk_tier},
        "participants": [{"id": s, "kind": "stakeholder"} for s in people],
        "roles": [{"id": "chair", "seat": "chair"}, {"id": "reviewer", "seat": "reviewer"}],
        "engagement": {"mode": "async", "rounds": 2},
        "budgets": {"tokens": 8000, "wall_s": 600},
        "evidence": {"required": ["artifact", "probe"]},
        "voting": {"rule": "majority", "quorum": 2},
        "stopping": {"expr": ("atom", "executable_test_settled", "eq", True)},
        "outcomes": {"accept": "ship", "reject": "rework"},
        "integrity": {"no_deliberation_in_blueprint": True},
        "artifacts": {"councilspec": "councilspec.json"},
        "execution": {"runtime": "phase7a-acceptor", "deliberation_executed": False},
        "meta": {"blueprint": "customer_council", "risk_tier": risk_tier},
    }
    return spec
