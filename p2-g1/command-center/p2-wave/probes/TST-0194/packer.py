#!/usr/bin/env python3
"""TST-0194 measured layer: package packer with a BUILD-TIME case-collision gate,
and an install step that silently loses colliding entries on NTFS (the
case-insensitive filesystem reality the build gate exists for)."""
from __future__ import annotations

import shutil
from pathlib import Path


class PackerBuildError(Exception):
    def __init__(self, message: str, colliding: list[str] | None = None):
        super().__init__(message)
        self.colliding = colliding or []


def find_case_collisions(entries: dict[str, bytes]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for path in entries:
        f = path.casefold()
        if f in seen and seen[f] != path:
            out.append((seen[f], path))
        else:
            seen.setdefault(f, path)
    return out


def build(entries: dict[str, bytes], staging: Path) -> Path:
    """BUILD step: rejects case-only duplicate entries BEFORE anything is written."""
    collisions = find_case_collisions(entries)
    if collisions:
        names = "; ".join("%r collides with %r" % (a, b) for a, b in collisions)
        raise PackerBuildError(
            "build failed: case-only duplicate manifest entries: " + names,
            colliding=[p for c in collisions for p in c],
        )
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for rel, data in entries.items():
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return staging


def install(staging: Path, target: Path) -> int:
    """INSTALL step: naive copy into a case-insensitive NTFS target.
    Returns the number of files ACTUALLY present after install."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for src in staging.rglob("*"):
        if src.is_file():
            dest = target / src.relative_to(staging)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    return sum(1 for f in target.rglob("*") if f.is_file())
