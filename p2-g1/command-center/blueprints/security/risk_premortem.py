"""Premortem halt on auto-loading agent config unless owner accepted that risk."""
from __future__ import annotations

from typing import Any

TRIGGER = "auto-loading agent config"


def premortem(plan: dict[str, Any]) -> dict[str, Any]:
    observed = [str(x).lower() for x in (plan.get("observed_triggers") or [])]
    accepted = [str(x).lower() for x in (plan.get("owner_accepted_risks") or [])]
    hit = any(TRIGGER in item for item in observed)
    accepted_hit = any(TRIGGER in item for item in accepted)
    halt = bool(hit) and not accepted_hit
    return {
        "plan_id": plan.get("plan_id"),
        "halt": halt,
        "trigger": TRIGGER if hit else None,
        "accepted": accepted_hit,
    }
