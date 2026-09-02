"""Run the customer-council blueprint: compose + accept, never deliberate."""
from __future__ import annotations

from typing import Any

from .compose import compose_council_spec, load_example
from .phase7a import RUNTIME_ID, validate_councilspec


def named_gates(spec: dict[str, Any]) -> list[str]:
    """Gate identifiers the acceptor can name from the spec without running it."""
    gates: list[str] = []
    rounds = (spec.get("engagement") or {}).get("rounds")
    if isinstance(rounds, int):
        gates.append(f"max-rounds-{rounds}")
    voting = spec.get("voting") or {}
    if voting.get("rule"):
        quorum = voting.get("quorum")
        gates.append(f"{voting['rule']}-advise" if quorum is None else f"{voting['rule']}-quorum-{quorum}")
    expr = (spec.get("stopping") or {}).get("expr")
    if isinstance(expr, (list, tuple)) and len(expr) >= 2 and expr[0] == "atom":
        gates.append(f"stop-when-{expr[1]}")
    return gates


def run_customer_council() -> dict[str, Any]:
    example = load_example()
    spec = compose_council_spec(
        question=example["question"],
        stakeholders=example["stakeholders"],
        risk_tier=example["risk_tier"],
    )
    report = validate_councilspec(spec)
    participants = [
        p.get("id") for p in spec.get("participants") or [] if isinstance(p, dict) and p.get("id")
    ]
    rounds = (spec.get("engagement") or {}).get("rounds")
    return {
        "councilspec": spec,
        "acceptance": {
            "accepted": bool(report.get("ok")),
            "deliberation_executed": False,
            "runtime": RUNTIME_ID,
            "named_participants": participants,
            "named_rounds": rounds,
            "named_gates": named_gates(spec),
            "schema_path": report.get("schema_path"),
            "live_schema": bool(report.get("live_schema")),
            "report": report,
        },
    }
