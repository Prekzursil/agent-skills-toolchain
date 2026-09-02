"""A8 muscle-memory disposition tables and partition check.

Product surface (from ARC-0052 question; A8 DESIGN.json is absent on this
tree): one command (/run), one cockpit (/cockpit), one catalog (/catalog).
skill.catalog is the skill that backs /catalog and is preserved as a name.
"""
from __future__ import annotations

from typing import Any

PRODUCT_NAMES = ("/run", "/cockpit", "/catalog", "skill.catalog")

# Old names the owner still types. Each resolves to a product surface.
ALIASES: dict[str, str] = {
    "/council": "/run",
    "/wf": "/run",
    "/workflow": "/run",
    "/status": "/cockpit",
    "/dash": "/cockpit",
    "/help": "/catalog",
    "skill.council": "/run",
    "monitor.fleet": "/cockpit",
    "scripts/run-council.py": "/run",
}

# Still invoke, but warn. Not removable until window + zero usage.
DEPRECATED: dict[str, str] = {
    "/old-repair": "/run",
    "/sync-live": "/cockpit",
    "skill.debug-dump": "/run",
    "monitor.heartbeat-legacy": "/cockpit",
    "scripts/sync-from-live.ps1": "/cockpit",
}

# Successors recorded so a removed name is never a silent drop.
REMOVED_SUCCESSORS: dict[str, str] = {
    "/tmp-scratch": "/run",
    "skill.scratch": "/catalog",
    "scripts/adhoc-once.sh": "/run",
}

DISPOSITIONS = ("preserved", "aliased", "deprecated", "removed")


def _conflicts() -> list[str]:
    bags = [set(PRODUCT_NAMES), set(ALIASES), set(DEPRECATED), set(REMOVED_SUCCESSORS)]
    seen: dict[str, int] = {}
    for i, bag in enumerate(bags):
        for name in bag:
            seen[name] = seen.get(name, 0) + 1
    return sorted(n for n, c in seen.items() if c > 1)


def classify(name: str) -> str | None:
    if name in PRODUCT_NAMES:
        return "preserved"
    if name in ALIASES:
        return "aliased"
    if name in DEPRECATED:
        return "deprecated"
    if name in REMOVED_SUCCESSORS:
        return "removed"
    return None


def target_of(name: str) -> str | None:
    kind = classify(name)
    if kind == "preserved":
        return name if name.startswith("/") else name
    if kind == "aliased":
        return ALIASES[name]
    if kind == "deprecated":
        return DEPRECATED[name]
    if kind == "removed":
        return REMOVED_SUCCESSORS[name]
    return None


def partition(names: list[str], usage: dict[str, int]) -> dict[str, Any]:
    """Assign every enumerated name exactly one disposition. Fail closed on gaps."""
    dup = _conflicts()
    if dup:
        raise RuntimeError(f"policy table overlap: {dup}")
    preserved: list[str] = []
    aliased: list[str] = []
    deprecated: list[str] = []
    removed: list[str] = []
    gaps: list[str] = []
    removal_blocked: list[dict[str, Any]] = []
    for name in names:
        kind = classify(name)
        if kind == "preserved":
            preserved.append(name)
        elif kind == "aliased":
            aliased.append(name)
        elif kind == "deprecated":
            deprecated.append(name)
        elif kind == "removed":
            count = int(usage.get(name, 0))
            if count != 0:
                removal_blocked.append({"name": name, "usage_in_window": count})
            removed.append(name)
        else:
            gaps.append(name)
    buckets = {
        "preserved": preserved,
        "aliased": aliased,
        "deprecated": deprecated,
        "removed": removed,
    }
    enumerated = set(names)
    union = set(preserved) | set(aliased) | set(deprecated) | set(removed)
    overlaps: list[str] = []
    seen: set[str] = set()
    for bag in buckets.values():
        for n in bag:
            if n in seen:
                overlaps.append(n)
            seen.add(n)
    totality = enumerated == union and not gaps and not overlaps
    return {
        "preserved": preserved,
        "aliased": aliased,
        "deprecated": deprecated,
        "removed": removed,
        "gaps": gaps,
        "overlaps": overlaps,
        "removal_blocked": removal_blocked,
        "totality_holds": bool(totality and not removal_blocked),
        "disjoint": not overlaps,
        "counts": {
            "enumerated": len(names),
            "preserved": len(preserved),
            "aliased": len(aliased),
            "deprecated": len(deprecated),
            "removed": len(removed),
        },
    }
