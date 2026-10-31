"""Casefold live-path intersection. Imports IMP-0022 casefold_key by identity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from plugin.casefold_paths import casefold_key


@dataclass(frozen=True)
class PathConflict:
    casefold_key: str
    claimants: tuple[tuple[str, str], ...]

    def named_packages(self) -> tuple[str, ...]:
        seen: list[str] = []
        for pkg, _path in self.claimants:
            if pkg not in seen:
                seen.append(pkg)
        return tuple(seen)

    def refuse_message(self) -> str:
        named = " and ".join(self.named_packages())
        paths = "; ".join(f"{pkg}:{path}" for pkg, path in self.claimants)
        return (
            "REFUSED: two packages would deploy to the same live path "
            f"(casefold_key={self.casefold_key!r}); claimants named: {named}; "
            f"paths: {paths}"
        )


def named_intersection(
    map_a: dict[str, str], map_b: dict[str, str]
) -> tuple[set[str], list[PathConflict]]:
    """maps are live_path -> package_id (or package_id values from project_payload)."""
    buckets: dict[str, list[tuple[str, str]]] = {}

    def add(live: str, pkg: str) -> None:
        key = casefold_key(live)
        buckets.setdefault(key, []).append((pkg, live))

    for live, pkg in (map_a or {}).items():
        add(str(live), str(pkg))
    for live, pkg in (map_b or {}).items():
        add(str(live), str(pkg))
    keys: set[str] = set()
    conflicts: list[PathConflict] = []
    for key, rows in buckets.items():
        pkgs = {p for p, _ in rows}
        if len(pkgs) < 2:
            continue
        keys.add(key)
        # unique (pkg, path) pairs
        seen: set[tuple[str, str]] = set()
        claimants: list[tuple[str, str]] = []
        for row in rows:
            if row not in seen:
                seen.add(row)
                claimants.append(row)
        conflicts.append(PathConflict(casefold_key=key, claimants=tuple(claimants)))
    return keys, conflicts


def conflicts_from_index(index: dict[str, Any]) -> list[PathConflict]:
    packages = index.get("packages") or []
    maps: list[dict[str, str]] = []
    for pkg in packages:
        pid = str(pkg.get("id") or "")
        payload_paths = pkg.get("payload_paths") or pkg.get("payload") or []
        m: dict[str, str] = {}
        if isinstance(payload_paths, dict):
            for rel in payload_paths:
                live = str(rel).replace("\\", "/")
                if not live.startswith(".claude/"):
                    live = ".claude/" + live.lstrip("/")
                m[live] = pid
        else:
            for rel in payload_paths:
                live = str(rel).replace("\\", "/")
                if not live.startswith(".claude/"):
                    live = ".claude/" + live.lstrip("/")
                m[live] = pid
        maps.append(m)
    acc: dict[str, str] = {}
    all_conflicts: list[PathConflict] = []
    seen_keys: set[str] = set()
    for m in maps:
        keys, conflicts = named_intersection(acc, m)
        for c in conflicts:
            if c.casefold_key not in seen_keys:
                seen_keys.add(c.casefold_key)
                all_conflicts.append(c)
        acc.update(m)
        del keys
    return all_conflicts
