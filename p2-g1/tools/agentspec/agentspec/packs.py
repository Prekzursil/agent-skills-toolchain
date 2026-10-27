"""Privilege-narrowing pack loader (IMP-0207).

A preset may only request a subset of the workflow's tools and sources.
Widening is a named PackViolation, never a silent clip.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentspec.semver import parse_semver


@dataclass
class PackViolation:
    code: str
    message: str
    extra: list[str] = field(default_factory=list)
    axis: str = ""
    ok: bool = False


@dataclass
class Binding:
    tool_permissions: frozenset[str]
    source_policy: frozenset[str]


@dataclass
class WorkflowView:
    id: str
    tool_permissions: list[str]
    source_policy: list[str]
    params: list[Any]


@dataclass
class PresetView:
    id: str
    requested_tool_permissions: list[str] | None
    requested_source_policy: list[str] | None


@dataclass
class LoadedPack:
    version: Any
    doc: dict[str, Any]

    def workflow(self, wf_id: str) -> WorkflowView:
        for wf in self.doc.get("workflows") or []:
            if wf.get("id") == wf_id:
                params = wf.get("params") or {}
                if isinstance(params, dict):
                    param_pairs = [(k, v) for k, v in params.items()]
                else:
                    param_pairs = list(params)
                return WorkflowView(
                    id=wf_id,
                    tool_permissions=list(wf.get("tool_permissions") or []),
                    source_policy=list(wf.get("source_policy") or []),
                    params=param_pairs,
                )
        raise KeyError(wf_id)

    def preset(self, preset_id: str) -> PresetView:
        for p in self.doc.get("presets") or []:
            if p.get("id") == preset_id:
                return PresetView(
                    id=preset_id,
                    requested_tool_permissions=list(p.get("tool_permissions") or []),
                    requested_source_policy=list(p.get("source_policy") or []),
                )
        raise KeyError(preset_id)

    def effective_for(self, wf_id: str, preset_id: str) -> Binding:
        wf = self.workflow(wf_id)
        preset = self.preset(preset_id)
        tools = privilege_intersection(
            frozenset(preset.requested_tool_permissions or []),
            frozenset(wf.tool_permissions),
        )
        sources = privilege_intersection(
            frozenset(preset.requested_source_policy or []),
            frozenset(wf.source_policy),
        )
        return Binding(tool_permissions=tools, source_policy=sources)


def privilege_intersection(left: frozenset[str], right: frozenset[str]) -> frozenset[str]:
    return frozenset(left) & frozenset(right)


def _as_doc(pack: Any) -> dict[str, Any]:
    if isinstance(pack, dict):
        return pack
    from pathlib import Path
    import json

    path = Path(pack)
    return json.loads(path.read_text(encoding="utf-8"))


def load_pack(pack: Any) -> LoadedPack | PackViolation:
    doc = _as_doc(pack)
    version = doc.get("version")
    parsed = parse_semver(str(version) if version is not None else "")
    if parsed is None:
        return PackViolation(
            code="pack-semver-invalid",
            message=f"invalid semver {version!r}",
        )
    workflows = list(doc.get("workflows") or [])
    wf_tools: dict[str, set[str]] = {}
    wf_sources: dict[str, set[str]] = {}
    for wf in workflows:
        wf_tools[str(wf.get("id"))] = set(wf.get("tool_permissions") or [])
        wf_sources[str(wf.get("id"))] = set(wf.get("source_policy") or [])
    ceiling_tools = set().union(*wf_tools.values()) if wf_tools else set()
    ceiling_sources = set().union(*wf_sources.values()) if wf_sources else set()
    for preset in doc.get("presets") or []:
        tools = set(preset.get("tool_permissions") or [])
        sources = set(preset.get("source_policy") or [])
        extra_tools = sorted(tools - ceiling_tools)
        extra_sources = sorted(sources - ceiling_sources)
        if extra_tools:
            return PackViolation(
                code="pack-preset-tool-permission-widening",
                message="preset requests tools outside the workflow ceiling",
                extra=extra_tools,
                axis="tool_permissions",
            )
        if extra_sources:
            return PackViolation(
                code="pack-preset-source-policy-widening",
                message="preset requests sources outside the workflow ceiling",
                extra=extra_sources,
                axis="source_policy",
            )
    return LoadedPack(version=parsed, doc=doc)


__all__ = [
    "Binding",
    "LoadedPack",
    "PackViolation",
    "load_pack",
    "privilege_intersection",
]
