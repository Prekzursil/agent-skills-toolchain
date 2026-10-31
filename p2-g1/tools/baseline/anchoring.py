"""Anchoring-kind declarations for baseline snapshot fields (TST-0023)."""
from __future__ import annotations

from typing import Any

ANCHORED_FIELD_NAMES = (
    "repo",
    "branches",
    "worktrees",
    "plugin_settings",
    "marketplaces",
    "skills",
    "mcps",
)
SAMPLED_FIELD_NAMES = (
    "kind",
    "captured_at",
    "live_deployments",
    "caches",
    "hooks",
    "hooks_tree",
)


def schema_anchoring_gaps(schema: dict[str, Any]) -> list[str]:
    props = schema.get("properties") or {}
    gaps: list[str] = []
    for name in list(ANCHORED_FIELD_NAMES) + list(SAMPLED_FIELD_NAMES):
        spec = props.get(name)
        if not isinstance(spec, dict):
            continue
        kind = spec.get("x-anchoring-kind") or spec.get("anchoring_kind")
        if name in ANCHORED_FIELD_NAMES and kind not in {"SHA-ANCHORED", None}:
            if kind != "SHA-ANCHORED":
                gaps.append(name)
        if name in SAMPLED_FIELD_NAMES and name not in {"kind", "captured_at"}:
            if kind not in {"SAMPLED-AT-TIME", None}:
                gaps.append(name)
    return gaps


def instance_sampled_timestamp_gaps(snap: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    gaps: list[str] = []
    for name in SAMPLED_FIELD_NAMES:
        if name in {"kind", "captured_at"}:
            continue
        obj = snap.get(name)
        if isinstance(obj, dict) and not obj.get("sampled_at"):
            gaps.append(name)
    return gaps
