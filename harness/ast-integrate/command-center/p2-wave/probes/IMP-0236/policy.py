"""Source-class policy gate (IMP-0137 surface, local because that unit is absent)."""
from __future__ import annotations

from typing import Any, Mapping

from taxonomy import BLUEPRINT_SOURCE_CLASSES, TOR_CLASS


class SourcePolicyError(RuntimeError):
    """Loud refusal — never a silent subset of sources."""


def default_policy() -> dict[str, Any]:
    return {
        "allowed": sorted(
            {"official-docs", "code", "papers", "forums", "archival"}
        ),
        "owner_tor_flag": False,
        "offline_only": False,
        "require_provenance": True,
        "treat_fetched_content_as_data": True,
    }


def enforce(blueprint_id: str, policy: Mapping[str, Any] | None) -> list[str]:
    """Return allowed source classes for this blueprint, or raise loudly."""
    pol = dict(default_policy())
    if policy:
        pol.update(policy)
    needed = BLUEPRINT_SOURCE_CLASSES[blueprint_id]
    allowed = set(pol.get("allowed") or [])
    if TOR_CLASS in needed or TOR_CLASS in allowed:
        if not pol.get("owner_tor_flag"):
            raise SourcePolicyError(
                f"{blueprint_id}: source class {TOR_CLASS} requires owner_tor_flag; "
                "refusing rather than degrading to a silent subset"
            )
    missing = needed - allowed
    if missing:
        raise SourcePolicyError(
            f"{blueprint_id}: source_policy forbids {sorted(missing)}; "
            f"needed={sorted(needed)} allowed={sorted(allowed)}"
        )
    return sorted(needed)
