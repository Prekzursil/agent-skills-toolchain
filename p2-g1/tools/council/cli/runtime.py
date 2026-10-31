"""Council CLI runtime helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.council.budget.preflight import (
    REASON_CEILING_BREACH,
    CouncilPlan,
    OwnerApproval,
    OwnerCeiling,
    estimate_cost,
    preflight,
)

COUNCIL_SUCCESS_SENTINEL = "SUCCESS:COUNCIL-RUN"


@dataclass
class CouncilResult:
    ok: bool
    reason: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)


def execute(spec: dict[str, Any]) -> CouncilResult:
    events: list[dict[str, Any]] = []
    ceiling_doc = spec.get("owner_ceiling")
    if ceiling_doc:
        plan = CouncilPlan.from_mapping(spec)
        ceiling = OwnerCeiling(
            tokens=int(ceiling_doc.get("tokens") or 0),
            wall_clock_seconds=float(ceiling_doc.get("wall_clock_seconds") or 0.0),
            external_calls=int(ceiling_doc.get("external_calls") or 0),
        )
        approval = None
        ap = spec.get("owner_approval")
        if isinstance(ap, dict):
            approval = OwnerApproval(
                granted=bool(ap.get("granted")),
                approver_id=str(ap.get("approver_id") or ""),
                ticket=str(ap.get("ticket") or ""),
                dimensions=tuple(ap.get("dimensions") or ()),
            )
        pf = preflight(plan, ceiling, approval)
        if not pf.allowed:
            events.append({"kind": "preflight-refuse", "reason": pf.reason})
            return CouncilResult(ok=False, reason=pf.reason, events=events)
        events.append({"kind": "preflight-ok", "reason": pf.reason})
    events.append({"kind": "vote", "rule": (spec.get("voting") or {}).get("rule")})
    events.append({"kind": "complete"})
    return CouncilResult(ok=True, reason="launched", events=events)
