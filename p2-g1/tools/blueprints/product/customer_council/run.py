"""Run the customer-council blueprint: compose + accept, never deliberate."""
from __future__ import annotations

from typing import Any

from .compose import compose_council_spec, load_example
from .phase7a import validate_councilspec


def run_customer_council() -> dict[str, Any]:
    example = load_example()
    spec = compose_council_spec(
        question=example["question"],
        stakeholders=example["stakeholders"],
        risk_tier=example["risk_tier"],
    )
    report = validate_councilspec(spec)
    return {
        "councilspec": spec,
        "acceptance": {
            "accepted": bool(report.get("ok")),
            "deliberation_executed": False,
            "report": report,
        },
    }
