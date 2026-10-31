#!/usr/bin/env python3
"""Pure planning logic for the social-hub multiplexer.

No I/O side effects beyond reading cache files that are handed in by path; the
collision/merge/routing computation is a pure function of the cache contents so
it can be unit-tested in isolation (no child processes, no sockets).

A *plan* answers three questions the runtime needs:
  * which tools does the merged ``tools/list`` expose (original names, plus a
    minimal backend prefix for cross-backend collisions only), and
  * for a given exposed tool name, which backend owns it and under what
    ORIGINAL name (so the call is rewritten before forwarding), and
  * which backends are degraded (no usable cache) so their tools can be flagged.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Iterable

from backends import BackendSpec


@dataclass(frozen=True)
class Route:
    """Resolution of one exposed tool name back to its owning backend."""

    backend_id: str
    original_name: str
    renamed: bool


@dataclass
class Plan:
    """The merged view served to the MCP client without spawning anything."""

    tools: list[dict] = field(default_factory=list)
    routing: dict[str, Route] = field(default_factory=dict)
    collisions: dict[str, list[str]] = field(default_factory=dict)
    degraded: dict[str, str] = field(default_factory=dict)  # backend_id -> reason


def load_cache(path: str) -> dict | None:
    """Read a per-backend cache file; return None if missing/unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def tools_of(cache: dict | None) -> list[dict]:
    """Extract the tool list from a cache dict (lazy_proxy cache shape)."""
    if not cache:
        return []
    tools = (cache.get("tools") or {}).get("tools")
    return tools if isinstance(tools, list) else []


def _name_owners(
    specs: Iterable[BackendSpec], tools_by_backend: dict[str, list[dict]]
) -> dict[str, list[str]]:
    """Map each original tool name to the list of backend ids exposing it."""
    owners: dict[str, list[str]] = {}
    for spec in specs:
        for tool in tools_by_backend.get(spec.id, []):
            name = tool.get("name")
            if isinstance(name, str) and name:
                owners.setdefault(name, []).append(spec.id)
    return owners


def build_plan(specs: list[BackendSpec], cache_dir: str) -> Plan:
    """Compute the merged plan from committed caches (no spawning)."""
    tools_by_backend: dict[str, list[dict]] = {}
    plan = Plan()
    for spec in specs:
        cache = load_cache(os.path.join(cache_dir, spec.cache))
        tools = tools_of(cache)
        tools_by_backend[spec.id] = tools
        if not tools:
            plan.degraded[spec.id] = "no cached tool list (backend never enumerated)"

    owners = _name_owners(specs, tools_by_backend)
    plan.collisions = {n: ids for n, ids in owners.items() if len(ids) > 1}

    seen: set[str] = set()
    by_id = {s.id: s for s in specs}
    for spec in specs:
        for tool in tools_by_backend[spec.id]:
            name = tool.get("name")
            if not isinstance(name, str) or not name:
                continue
            collides = len(owners.get(name, [])) > 1
            exposed = f"{spec.prefix}_{name}" if collides else name
            if exposed in seen:
                # Extremely defensive: a prefixed name re-collided. Disambiguate
                # further with the full backend id so the surface stays unique.
                exposed = f"{spec.id}_{name}"
            seen.add(exposed)
            plan.routing[exposed] = Route(spec.id, name, exposed != name)
            merged_tool = dict(tool)
            merged_tool["name"] = exposed
            if collides:
                origin = by_id[spec.id].label
                base = merged_tool.get("description") or ""
                merged_tool["description"] = (
                    f"[{origin}] {base}".strip()
                    + f"  (exposed as '{exposed}'; original name '{name}' collides across backends)"
                )
            plan.tools.append(merged_tool)
    return plan
