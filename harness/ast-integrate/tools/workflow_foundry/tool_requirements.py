"""Typed tool requirements vs host grantable set (IMP-0167)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


def extract_tool_requirements(candidate: Mapping[str, Any]) -> set[str]:
    found: set[str] = set()
    for stage in candidate.get("stages") or []:
        if isinstance(stage, Mapping):
            for tool in stage.get("tools") or []:
                found.add(str(tool))
    for role in candidate.get("roles") or []:
        if isinstance(role, Mapping):
            for tool in role.get("tools") or []:
                found.add(str(tool))
    for tool in candidate.get("tools") or []:
        found.add(str(tool))
    typed = candidate.get("required_tools") or candidate.get("tool_requirements")
    if isinstance(typed, (list, tuple, set)):
        found.update(str(t) for t in typed)
    return found


def reconcile_subset(required: Iterable[str], grantable: Iterable[str]) -> list[str]:
    grant = set(grantable)
    return sorted(str(r) for r in required if str(r) not in grant)


@dataclass
class ImportResult:
    status: str
    method: str = "set-subset"
    missing_capabilities: list[str] = field(default_factory=list)
    missing_from_host: list[str] = field(default_factory=list)
    missing_from_unit: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "method": self.method,
            "missing_capabilities": list(self.missing_capabilities),
            "missing_from_host": list(self.missing_from_host),
            "missing_from_unit": list(self.missing_from_unit),
        }


def import_candidate(
    candidate: Mapping[str, Any],
    *,
    unit_permissions: Sequence[str] | None = None,
    host_grantable: Sequence[str] | None = None,
) -> ImportResult:
    required = extract_tool_requirements(candidate)
    host = set(host_grantable or [])
    unit = set(unit_permissions or [])
    grantable = host | unit
    missing_host = reconcile_subset(required, host)
    missing_unit = reconcile_subset(required, unit)
    missing = reconcile_subset(required, grantable)
    if missing:
        return ImportResult(
            status="BLOCKED",
            missing_capabilities=missing,
            missing_from_host=missing_host,
            missing_from_unit=missing_unit,
        )
    return ImportResult(status="IMPORTED")
