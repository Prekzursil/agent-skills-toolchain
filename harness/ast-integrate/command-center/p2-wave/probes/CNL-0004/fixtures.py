"""CNL-0004 fixtures: conflict, unsatisfiable, and agree (negative control)."""
from __future__ import annotations

from typing import Any

TASK_CONFLICT: dict[str, Any] = {
    "id": "cnl-0004-conflict",
    "title": "Architecture review of a payment-authorization service",
    "risk_tier": "high",
    "domain": "payments",
}

TASK_UNSAT: dict[str, Any] = {
    "id": "cnl-0004-unsatisfiable",
    "title": "Architecture review of a payment-authorization service",
    "risk_tier": "high",
    "domain": "payments",
}

TASK_AGREE: dict[str, Any] = {
    "id": "cnl-0004-agree",
    "title": "Architecture review of a payment-authorization service",
    "risk_tier": "high",
    "domain": "payments",
}

# Auto-composer spends 48 USD and uses web-search, no human.
# Owner: cheaper ceiling, ban web-search, require a human security seat.
CONSTRAINTS_CONFLICT: list[dict[str, Any]] = [
    {
        "constraint_id": "OC-BUDGET",
        "constraint_class": "budget_ceiling",
        "max_usd": 40.0,
    },
    {
        "constraint_id": "OC-NOSRC",
        "constraint_class": "forbidden_source_class",
        "source_class": "web-search",
    },
    {
        "constraint_id": "OC-HUMAN",
        "constraint_class": "mandatory_human_seat",
        "role": "security-reviewer-human",
        "seat_id": "human.security",
    },
]

# Human seat costs 10; ceiling 5 cannot fit even after dropping every model.
CONSTRAINTS_UNSAT: list[dict[str, Any]] = [
    {
        "constraint_id": "OC-BUDGET-TIGHT",
        "constraint_class": "budget_ceiling",
        "max_usd": 5.0,
    },
    {
        "constraint_id": "OC-HUMAN",
        "constraint_class": "mandatory_human_seat",
        "role": "security-reviewer-human",
        "seat_id": "human.security",
    },
]

# Ceiling above auto spend; forbidden class auto never used; no human required.
CONSTRAINTS_AGREE: list[dict[str, Any]] = [
    {
        "constraint_id": "OC-BUDGET-LOOSE",
        "constraint_class": "budget_ceiling",
        "max_usd": 100.0,
    },
    {
        "constraint_id": "OC-NOCRAWL",
        "constraint_class": "forbidden_source_class",
        "source_class": "unlicensed-crawl",
    },
]

INVALID_CONSTRAINT: dict[str, Any] = {
    "constraint_id": "OC-BROKEN",
    "max_usd": 10.0,
}
