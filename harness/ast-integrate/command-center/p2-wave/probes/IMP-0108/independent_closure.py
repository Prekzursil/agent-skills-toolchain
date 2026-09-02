#!/usr/bin/env python3
"""Independent required-closure walk for IMP-0108 probe 2.

This is a BFS over `kind=required` edges. It does not import
marketplace.resolver, so agreement with export is a second computation,
not the exporter echoing itself.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable


def pkg_id(name: str, version: str) -> str:
    return f"{name}@{version}"


def independent_required_closure(
    index: dict[str, Any],
    selection: Iterable[tuple[str, str]],
) -> list[str]:
    table = {
        pkg_id(str(p["name"]), str(p["version"])): p
        for p in (index.get("packages") or [])
        if isinstance(p, dict)
    }
    seen: set[str] = set()
    q: deque[str] = deque()
    for name, version in selection:
        q.append(pkg_id(name, version))
    missing: list[str] = []
    while q:
        pid = q.popleft()
        if pid in seen:
            continue
        rec = table.get(pid)
        if rec is None:
            missing.append(pid)
            continue
        seen.add(pid)
        deps = list(rec.get("dependencies") or [])
        deps.sort(key=lambda d: (str(d.get("name")), str(d.get("version"))))
        for dep in deps:
            if not isinstance(dep, dict):
                continue
            if str(dep.get("kind") or "required") != "required":
                continue
            q.append(pkg_id(str(dep["name"]), str(dep["version"])))
    if missing:
        raise RuntimeError(f"independent walk missing {missing}")
    return sorted(seen)
