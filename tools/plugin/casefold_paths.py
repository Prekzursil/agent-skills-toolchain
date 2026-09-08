#!/usr/bin/env python3
"""Path-casing normalisation and casefold collision detection (IMP-0022).

Normalisation contract (reviewer-facing, do not drift):

1. Unify separators to ``/``.
2. Apply Unicode **NFC** normalisation first (``unicodedata.normalize("NFC", …)``).
3. Apply Python ``str.casefold()`` — **not** ``str.lower()`` — to produce the
   collision key.

Two payload paths that share a key after that pipeline are legal on a
case-sensitive Linux tree but collide on default Windows/macOS filesystems,
where the second write silently overwrites the first.

Signal (1) of the catalog evidence requirement is the set-collision count over
the payload path list. Signal (2) requires extracting the archive onto a real
case-insensitive filesystem and comparing extracted file count to archive
entry count — a collision shows up as a shortfall. A case-sensitive host
cannot supply signal (2); callers must fail closed rather than invent it.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


class CasefoldCollisionError(RuntimeError):
    """Two or more payload paths collide under NFC+casefold."""

    exit_code = 14

    def __init__(self, groups: Sequence["CollisionGroup"]):
        self.groups = list(groups)
        parts = [
            f"casefold collision group key={g.key!r} paths={list(g.paths)}"
            for g in self.groups
        ]
        super().__init__(
            "NFC+casefold path collisions detected "
            f"(groups={len(self.groups)}):\n" + "\n".join(parts)
        )


@dataclass(frozen=True)
class CollisionGroup:
    """One NFC+casefold key shared by two or more distinct exact paths."""

    key: str
    paths: tuple[str, ...]


@dataclass
class CasefoldReport:
    """Result of scanning a path set for NFC+casefold collisions."""

    paths: list[str]
    keys: dict[str, str] = field(default_factory=dict)
    collisions: list[CollisionGroup] = field(default_factory=list)

    @property
    def collision_count(self) -> int:
        return len(self.collisions)

    @property
    def colliding_path_count(self) -> int:
        return sum(len(g.paths) for g in self.collisions)

    def as_dict(self) -> dict:
        return {
            "path_count": len(self.paths),
            "collision_group_count": self.collision_count,
            "colliding_path_count": self.colliding_path_count,
            "collisions": [
                {"key": g.key, "paths": list(g.paths)} for g in self.collisions
            ],
            "normalisation": "NFC then str.casefold (not str.lower)",
        }


def nfc_path(path: str) -> str:
    """Unify separators and apply Unicode NFC. Does not casefold."""
    return unicodedata.normalize("NFC", path.replace("\\", "/"))


def casefold_key(path: str) -> str:
    """Documented collision key: NFC first, then ``str.casefold()`` (not lower)."""
    return nfc_path(path).casefold()


def find_casefold_collisions(paths: Iterable[str]) -> CasefoldReport:
    """Compute NFC+casefold collision groups over ``paths``.

    Exact-duplicate paths are de-duplicated before grouping so a repeated
    listing of the same path does not count as a cross-filesystem collision.
    Distinct strings that share a casefold key do.
    """
    exact: list[str] = []
    seen_exact: set[str] = set()
    for raw in paths:
        rel = nfc_path(raw)
        if rel in seen_exact:
            continue
        seen_exact.add(rel)
        exact.append(rel)

    buckets: dict[str, list[str]] = defaultdict(list)
    keys: dict[str, str] = {}
    for rel in exact:
        key = casefold_key(rel)
        keys[rel] = key
        buckets[key].append(rel)

    collisions = [
        CollisionGroup(key=key, paths=tuple(sorted(members)))
        for key, members in sorted(buckets.items())
        if len(members) > 1
    ]
    return CasefoldReport(paths=exact, keys=keys, collisions=collisions)


def assert_no_casefold_collisions(paths: Iterable[str]) -> CasefoldReport:
    """Fail closed when any NFC+casefold collision group exists."""
    report = find_casefold_collisions(paths)
    if report.collisions:
        raise CasefoldCollisionError(report.collisions)
    return report


def filesystem_is_case_insensitive(probe_dir: Path | str | None = None) -> bool:
    """Return True when the filesystem under ``probe_dir`` collapses case.

    Creates two sibling names that differ only by case. On a case-insensitive
    volume the second create lands on the first inode; on a case-sensitive
    volume both exist as distinct files.
    """
    root = Path(probe_dir) if probe_dir is not None else Path(tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    scratch = Path(
        tempfile.mkdtemp(prefix="imp0022-ci-probe-", dir=str(root))
    )
    try:
        upper = scratch / "IMP0022CaseProbe.TXT"
        lower = scratch / "imp0022caseprobe.txt"
        upper.write_bytes(b"UPPER")
        # Second write: on CI-FS this overwrites; on CS-FS this is a new file.
        lower.write_bytes(b"lower")
        names = sorted(p.name for p in scratch.iterdir())
        if len(names) == 1:
            return True
        # Some CI-FS implementations keep the first casing in the directory
        # listing but still share an inode.
        try:
            return os.path.samefile(upper, lower)
        except OSError:
            return False
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


@dataclass
class ExtractCountResult:
    """Archive entry count vs files present after extraction."""

    archive: str
    dest: str
    archive_entry_count: int
    extracted_file_count: int
    shortfall: int
    case_insensitive_dest: bool
    planted_collision_paths: list[str] = field(default_factory=list)

    @property
    def collision_shortfall_observed(self) -> bool:
        return self.shortfall > 0

    def as_dict(self) -> dict:
        return {
            "archive": self.archive,
            "dest": self.dest,
            "archive_entry_count": self.archive_entry_count,
            "extracted_file_count": self.extracted_file_count,
            "shortfall": self.shortfall,
            "case_insensitive_dest": self.case_insensitive_dest,
            "collision_shortfall_observed": self.collision_shortfall_observed,
            "planted_collision_paths": list(self.planted_collision_paths),
        }


def extract_and_count(
    archive: Path | str,
    dest: Path | str,
    *,
    require_case_insensitive: bool = True,
) -> ExtractCountResult:
    """Extract ``archive`` into ``dest`` and compare file counts.

    Catalog signal (2): on a case-insensitive filesystem, colliding members
    overwrite each other and ``extracted_file_count < archive_entry_count``.

    When ``require_case_insensitive`` is True and ``dest`` is case-sensitive,
    raises ``RuntimeError`` naming the missing substrate — never invent a
    shortfall on a case-sensitive volume.
    """
    archive_p = Path(archive)
    dest_p = Path(dest)
    dest_p.mkdir(parents=True, exist_ok=True)
    ci = filesystem_is_case_insensitive(dest_p)
    if require_case_insensitive and not ci:
        raise RuntimeError(
            "IMP-0022 signal (2) requires extraction onto a case-insensitive "
            f"filesystem; dest={dest_p} is case-sensitive "
            f"(host_os={os.name!r}, probe=sibling UPPER/lower create)."
        )

    with zipfile.ZipFile(archive_p, "r") as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        zf.extractall(dest_p)

    extracted = [p for p in dest_p.rglob("*") if p.is_file()]
    shortfall = max(0, len(names) - len(extracted))
    return ExtractCountResult(
        archive=str(archive_p),
        dest=str(dest_p),
        archive_entry_count=len(names),
        extracted_file_count=len(extracted),
        shortfall=shortfall,
        case_insensitive_dest=ci,
    )


def write_collision_zip(
    members: Sequence[tuple[str, bytes]],
    out: Path | str,
) -> Path:
    """Write a zip whose member names are taken verbatim (for planted fixtures)."""
    out_p = Path(out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, blob in members:
            zf.writestr(nfc_path(name), blob)
    return out_p
