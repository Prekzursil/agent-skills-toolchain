"""Grant extraction and wildcard expansion for ARC-0006.

Declared grants are literal strings the A1 loader returns as data.
Effective grants are a probe-side expansion against an inventory: A1 itself
has no evaluator (DESIGN precedence.loader). Printing both is required so
we do not pretend the loader expanded '*'.
"""
from __future__ import annotations

import fnmatch
from typing import Any


def is_wildcard(token: str) -> bool:
    return any(ch in str(token) for ch in "*?[")


def _allow_list(node: Any) -> list[str]:
    if not isinstance(node, dict):
        return []
    policy = node.get("tool_policy")
    if isinstance(policy, dict) and isinstance(policy.get("allow"), list):
        return [str(x) for x in policy["allow"]]
    tools = node.get("tools")
    if isinstance(tools, list) and tools and all(isinstance(x, str) for x in tools):
        return [str(x) for x in tools]
    return []


def collect_declared(loaded: list[dict[str, Any]]) -> dict[str, Any]:
    tools: list[str] = []
    hooks: list[dict[str, str]] = []
    mounts: list[dict[str, Any]] = []
    for body in loaded:
        kind = str(body.get("kind") or "")
        cid = str(body.get("id") or "")
        tools.extend(_allow_list(body))
        if kind == "hook" or body.get("event") or body.get("event") or body.get("script") or body.get("script"):
            hooks.append(
                {
                    "id": cid,
                    "event": str(body.get("event") or body.get("event") or ""),
                    "script": str(body.get("script") or body.get("script") or ""),
                    "enabled": str(body.get("enabled", True)),
                }
            )
        if kind == "mcp_mount" or body.get("server") or body.get("transport"):
            mounts.append(
                {
                    "id": cid,
                    "server": str(body.get("server") or ""),
                    "tools": _allow_list(body),
                }
            )
    # Preserve order, drop empties.
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return {
        "tools": ordered,
        "wildcards": [t for t in ordered if is_wildcard(t)],
        "hooks": hooks,
        "mounts": mounts,
        "loaded_ids": [str(b.get("id") or "") for b in loaded],
    }


def expand_fnmatch(declared: list[str], inventory: list[str]) -> list[str]:
    out: set[str] = set()
    for pat in declared:
        matched = False
        for tool in inventory:
            if fnmatch.fnmatch(tool, pat):
                out.add(tool)
                matched = True
        if not matched and not is_wildcard(pat):
            out.add(pat)
    return sorted(out)


def expand_prefix(declared: list[str], inventory: list[str]) -> list[str]:
    """Mechanically different expander used by the second reviewer."""
    out: set[str] = set()
    for pat in declared:
        if pat == "*":
            out.update(inventory)
            continue
        if pat.endswith("*") and "*" not in pat[:-1]:
            prefix = pat[:-1]
            hits = [t for t in inventory if t.startswith(prefix)]
            out.update(hits if hits else [pat])
            continue
        if pat in inventory or not is_wildcard(pat):
            out.add(pat)
            continue
        # Fallback: treat remaining wildcards as literals (honest disagreement zone).
        out.add(pat)
    return sorted(out)
