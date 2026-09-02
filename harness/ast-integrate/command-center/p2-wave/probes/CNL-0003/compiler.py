#!/usr/bin/env python3
"""Charter-block compiler: protocol auto-select from ENUM branch keys only.

Closed axis maps are total functions. Lookup is dict[key], never dict.get(key, default).
Unknown or missing enum values COMPILE_REJECT. Prose fields never enter protocol_id.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# Compiler-branch keys. Values are protocol-family tokens, not 12-COUNCIL card
# names (that catalogue is absent on this worktree; see emit.py residual).
RISK_FAMILY: dict[str, str] = {
    "low": "consult",
    "medium": "deliberate",
    "high": "adversarial",
    "critical": "owner_gated",
}
OUTPUT_FAMILY: dict[str, str] = {
    "decision": "vote",
    "ranked_options": "rank",
    "specification": "draft",
    "review": "review",
    "counterexample": "refute",
    "plan": "plan",
}
INTENT_FAMILY: dict[str, str] = {
    "unanimous": "unanimous",
    "supermajority": "supermajority",
    "majority": "majority",
    "owner_decides": "advise",
    "dissent_required": "dissent",
}

ENUM_FIELDS: dict[str, tuple[str, ...]] = {
    "risk_tier": tuple(RISK_FAMILY.keys()),
    "desired_output": tuple(OUTPUT_FAMILY.keys()),
    "consensus_intent": tuple(INTENT_FAMILY.keys()),
}
PROSE_FIELDS: tuple[str, ...] = ("objective", "success_criteria")
AXIS_MAPS: dict[str, dict[str, str]] = {
    "risk_tier": RISK_FAMILY,
    "desired_output": OUTPUT_FAMILY,
    "consensus_intent": INTENT_FAMILY,
}

ABSENT_CRITERIA_TOKEN = "success_criteria_absent_used_protocol_default"
REJECT = "COMPILE_REJECT"


@dataclass(frozen=True)
class CompileResult:
    ok: bool
    protocol_id: str | None
    reason: str
    fallbacks: tuple[str, ...] = field(default_factory=tuple)
    task_prose: str | None = None
    human_success_criteria: str | None = None

    def fired(self) -> bool:
        return not self.ok


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return ""


def _enum_lookup(field: str, raw: Any) -> tuple[str | None, str | None]:
    """Return (family_token, None) or (None, reject_reason). No default arm."""
    axis = AXIS_MAPS[field]
    key = _as_str(raw)
    if not key:
        return None, f"missing_enum:{field}"
    if key not in axis:
        return None, f"unknown_enum:{field}:{key}"
    return axis[key], None


def _read(charter: Mapping[str, Any], name: str) -> Any:
    if name in charter:
        return charter[name]
    return None


def select(charter: Mapping[str, Any]) -> CompileResult:
    """Auto-select a protocol family. Total over the enum cartesian product."""
    objective = _as_str(_read(charter, "objective"))
    if not objective:
        return CompileResult(
            ok=False,
            protocol_id=None,
            reason="objective_required",
            fallbacks=("prose_field_cannot_branch:objective",),
        )

    reasons: list[str] = []
    parts: list[str] = []
    for field in ("risk_tier", "desired_output", "consensus_intent"):
        token, err = _enum_lookup(field, _read(charter, field))
        if err:
            reasons.append(err)
        else:
            assert token is not None
            parts.append(token)
    if reasons:
        return CompileResult(
            ok=False,
            protocol_id=None,
            reason=reasons[0],
            fallbacks=tuple(reasons),
            task_prose=objective,
        )

    fallbacks: list[str] = ["prose_field_cannot_branch:objective"]
    criteria = _as_str(_read(charter, "success_criteria"))
    human: str | None
    if not criteria:
        fallbacks.append(ABSENT_CRITERIA_TOKEN)
        human = None
    else:
        fallbacks.append("prose_field_cannot_branch:success_criteria")
        human = criteria

    return CompileResult(
        ok=True,
        protocol_id=".".join(parts),
        reason="selected",
        fallbacks=tuple(fallbacks),
        task_prose=objective,
        human_success_criteria=human,
    )


def losing_select(charter: Mapping[str, Any]) -> CompileResult:
    """Losing option: treat every field as prose and silent-default the protocol.

    Implemented far enough that the branch-table / both-states checks can
    demonstrate the exact failure (unknown enum still yields a protocol).
    """
    risk = _as_str(charter.get("risk_tier")) or "low"
    output = _as_str(charter.get("desired_output")) or "decision"
    intent = _as_str(charter.get("consensus_intent")) or "majority"
    r = RISK_FAMILY.get(risk, "consult")
    o = OUTPUT_FAMILY.get(output, "vote")
    i = INTENT_FAMILY.get(intent, "majority")
    return CompileResult(
        ok=True,
        protocol_id=f"{r}.{o}.{i}",
        reason="silent_default",
        fallbacks=("losing_option_silent_default",),
        task_prose=_as_str(charter.get("objective")) or None,
        human_success_criteria=_as_str(charter.get("success_criteria")) or None,
    )


def cartesian_protocol_ids() -> dict[tuple[str, str, str], str]:
    table: dict[tuple[str, str, str], str] = {}
    for risk in RISK_FAMILY:
        for output in OUTPUT_FAMILY:
            for intent in INTENT_FAMILY:
                table[(risk, output, intent)] = (
                    f"{RISK_FAMILY[risk]}.{OUTPUT_FAMILY[output]}.{INTENT_FAMILY[intent]}"
                )
    return table


def good_charter(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "objective": "Decide whether the typed charter block is sufficient to auto-select a protocol.",
        "risk_tier": "medium",
        "desired_output": "decision",
        "success_criteria": "Every enum value routes; unknown enum COMPILE_REJECTs.",
        "consensus_intent": "majority",
    }
    base.update(overrides)
    return base
