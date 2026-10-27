"""Yank semantics: lockfile pins stay resolvable; fresh installs skip yanked."""
from __future__ import annotations

from dataclasses import dataclass

from tools.marketplace.semver_npm import max_satisfying, parse


@dataclass(frozen=True)
class PackageRelease:
    version: str
    yanked: bool = False


def resolve_from_lockfile(pinned: str, releases: list[PackageRelease]) -> str | None:
    for rel in releases:
        if rel.version == pinned:
            return pinned
    return None


def resolve_fresh_install(range_expr: str, releases: list[PackageRelease]) -> str | None:
    live = [r.version for r in releases if not r.yanked and parse(r.version)]
    return max_satisfying(live, range_expr)
