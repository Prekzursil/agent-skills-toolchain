"""Naive vs hardened file walkers and packagers for CNF-0152.

Naive implementations are deliberately broken the way each hostile shape
breaks real Windows-era code (MAX_PATH skip, relpath device crash swallowed
to zero, case-fold dict, ASCII encode skip, split-on-space).

Hardened implementations never convert a crash into a count of 0, never
silently drop a distinct name, and never fragment a path on spaces.
"""
from __future__ import annotations

import io
import os
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from shapes import (
    WIN_MAX_PATH,
    naive_win_relpath,
    naive_win_strip_trailing,
)

WalkFn = Callable[[Path], "WalkResult"]


@dataclass
class WalkResult:
    impl: str
    files: list[str]
    count: int
    crashed: bool
    swallowed_to_zero: bool
    error: str | None
    notes: list[str] = field(default_factory=list)
    collisions: list[dict] = field(default_factory=list)
    archive_members: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "impl": self.impl,
            "count": self.count,
            "files": self.files,
            "crashed": self.crashed,
            "swallowed_to_zero": self.swallowed_to_zero,
            "error": self.error,
            "notes": self.notes,
            "collisions": self.collisions,
            "archive_members": self.archive_members,
        }


def _relposix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_files(root: Path) -> list[Path]:
    """Independent enumerator: os.walk, no relpath, no MAX_PATH cap."""
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            out.append(Path(dirpath) / name)
    return out


def posix_live_walk(root: Path) -> WalkResult:
    """Live POSIX walk this Linux box actually performs (os.walk + relpath)."""
    files: list[str] = []
    try:
        for path in iter_files(root):
            files.append(os.path.relpath(path, root).replace(os.sep, "/"))
    except Exception as exc:  # pragma: no cover - POSIX should not raise
        return WalkResult(
            impl="posix-os.walk+os.path.relpath",
            files=[],
            count=0,
            crashed=True,
            swallowed_to_zero=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    return WalkResult(
        impl="posix-os.walk+os.path.relpath",
        files=files,
        count=len(files),
        crashed=False,
        swallowed_to_zero=False,
        error=None,
        notes=["POSIX relpath does not raise on a file named NUL"],
    )


def naive_walk_longpath(root: Path) -> WalkResult:
    """Skip any absolute path whose length exceeds 260 (legacy MAX_PATH)."""
    kept: list[str] = []
    skipped = 0
    for path in iter_files(root):
        if len(str(path)) > WIN_MAX_PATH or len(str(root)) > WIN_MAX_PATH:
            skipped += 1
            continue
        kept.append(_relposix(root, path))
    return WalkResult(
        impl="naive-max-path-260",
        files=kept,
        count=len(kept),
        crashed=False,
        swallowed_to_zero=False,
        error=None,
        notes=[f"skipped_over_max_path={skipped}", f"root_len={len(str(root))}"],
    )


def naive_walk_reserved_swallow(root: Path) -> WalkResult:
    """Phase-0 defect: one reserved-name relpath crash zeros the whole count."""
    files: list[str] = []
    try:
        for path in iter_files(root):
            rel = naive_win_relpath(str(path), str(root))
            files.append(rel.replace(os.sep, "/"))
        return WalkResult(
            impl="naive-win-relpath-swallow-whole-walk",
            files=files,
            count=len(files),
            crashed=False,
            swallowed_to_zero=False,
            error=None,
        )
    except ValueError as exc:
        return WalkResult(
            impl="naive-win-relpath-swallow-whole-walk",
            files=[],
            count=0,
            crashed=True,
            swallowed_to_zero=True,
            error=f"{type(exc).__name__}: {exc}",
            notes=[
                "swallowed reserved-device crash; entire walk reported as 0 files",
                "Phase-0 interpretation hazard: empty trees",
            ],
        )


def naive_walk_casefold(root: Path) -> WalkResult:
    """Case-insensitive dict silently keeps one of two case-distinct siblings."""
    folded: dict[str, str] = {}
    collisions: list[dict] = []
    for path in iter_files(root):
        rel = _relposix(root, path)
        key = rel.lower()
        if key in folded and folded[key] != rel:
            collisions.append({"kept": folded[key], "dropped": rel, "key": key})
        folded[key] = rel
    return WalkResult(
        impl="naive-casefold-dict",
        files=sorted(folded.values()),
        count=len(folded),
        crashed=False,
        swallowed_to_zero=False,
        error=None,
        notes=["case-insensitive key silently dropped a sibling"] if collisions else [],
        collisions=collisions,
    )


def naive_walk_ascii(root: Path) -> WalkResult:
    kept: list[str] = []
    dropped = 0
    for path in iter_files(root):
        rel = _relposix(root, path)
        try:
            rel.encode("ascii")
        except UnicodeEncodeError:
            dropped += 1
            continue
        kept.append(rel)
    return WalkResult(
        impl="naive-ascii-encode-skip",
        files=kept,
        count=len(kept),
        crashed=False,
        swallowed_to_zero=False,
        error=None,
        notes=[f"dropped_non_ascii={dropped}"],
    )


def naive_walk_spaces(root: Path) -> WalkResult:
    """Shell-split packaging: a path with spaces is not a single member."""
    members: list[str] = []
    originals: list[str] = []
    for path in iter_files(root):
        rel = _relposix(root, path)
        originals.append(rel)
        members.extend(rel.split())
    intact = [r for r in originals if " " in r and r in members]
    return WalkResult(
        impl="naive-split-on-space",
        files=members,
        count=len(members),
        crashed=False,
        swallowed_to_zero=False,
        error=None,
        notes=[
            f"original_paths={len(originals)}",
            f"spaced_paths_intact_as_members={len(intact)}",
        ],
        archive_members=members,
    )


def naive_walk_trailing_strip(root: Path) -> WalkResult:
    folded: dict[str, str] = {}
    collisions: list[dict] = []
    for path in iter_files(root):
        rel = _relposix(root, path)
        stripped = "/".join(
            naive_win_strip_trailing(part) for part in rel.split("/")
        )
        if stripped in folded and folded[stripped] != rel:
            collisions.append(
                {"kept": folded[stripped], "dropped": rel, "key": stripped}
            )
        folded[stripped] = rel
    return WalkResult(
        impl="naive-win-strip-trailing-dot-space",
        files=sorted(folded.keys()),
        count=len(folded),
        crashed=False,
        swallowed_to_zero=False,
        error=None,
        collisions=collisions,
        notes=[f"stripped_collision_count={len(collisions)}"],
    )


def naive_for_shape(shape_id: str) -> WalkFn:
    return {
        "a-long-root": naive_walk_longpath,
        "b-reserved-device": naive_walk_reserved_swallow,
        "c-case-collision": naive_walk_casefold,
        "d-non-ascii": naive_walk_ascii,
        "e-spaces": naive_walk_spaces,
        "f-trailing-dot-space": naive_walk_trailing_strip,
    }[shape_id]


def hardened_package(root: Path, rels: Iterable[str]) -> list[str]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        for rel in rels:
            zf.writestr(rel, (root / rel).read_bytes())
    with zipfile.ZipFile(buf, "r") as zf:
        return zf.namelist()


def hardened_walk(root: Path) -> WalkResult:
    """Survive all five catalog shapes plus the sixth.

    Per-entry errors are recorded. A single reserved-name failure cannot
    zero the walk. Case-distinct and trailing-dot-stripped names are kept
    as distinct members and collisions are reported rather than dropped.
    """
    files: list[str] = []
    errors: list[str] = []
    by_case: dict[str, list[str]] = defaultdict(list)
    by_stripped: dict[str, list[str]] = defaultdict(list)
    for path in iter_files(root):
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        files.append(rel)
        by_case[rel.lower()].append(rel)
        stripped = "/".join(
            naive_win_strip_trailing(part) for part in rel.split("/")
        )
        by_stripped[stripped].append(rel)

    collisions: list[dict] = []
    for key, names in sorted(by_case.items()):
        if len(set(names)) > 1:
            collisions.append({"kind": "case", "key": key, "names": names})
    for key, names in sorted(by_stripped.items()):
        if len(set(names)) > 1:
            collisions.append(
                {"kind": "trailing-strip", "key": key, "names": names}
            )

    if errors and not files:
        return WalkResult(
            impl="hardened-per-entry",
            files=[],
            count=0,
            crashed=True,
            swallowed_to_zero=False,
            error="; ".join(errors),
            notes=["errors recorded; not converted to a silent empty tree"],
            collisions=collisions,
        )

    archive_members = hardened_package(root, files)
    return WalkResult(
        impl="hardened-per-entry",
        files=files,
        count=len(files),
        crashed=False,
        swallowed_to_zero=False,
        error=None if not errors else "; ".join(errors),
        notes=[
            f"per_entry_errors={len(errors)}",
            "crash-cannot-become-count-0",
            f"zip_members={len(archive_members)}",
        ],
        collisions=collisions,
        archive_members=archive_members,
    )


def naive_breaks_shape(
    shape_id: str, root: Path, oracle_count: int
) -> tuple[bool, str, WalkResult]:
    """True when the naive impl fails this shape (known-broken control)."""
    result = naive_for_shape(shape_id)(root)
    if shape_id == "a-long-root":
        ok = result.count == 0 and oracle_count > 0
        why = "naive MAX_PATH skip dropped every file under a >260-char root"
    elif shape_id == "b-reserved-device":
        ok = (
            result.swallowed_to_zero
            and result.count == 0
            and result.crashed
            and result.error is not None
            and "NUL" in result.error
        )
        why = "naive swallow converted reserved-name crash into count 0"
    elif shape_id == "c-case-collision":
        ok = result.count < oracle_count and any(
            c.get("dropped") for c in result.collisions
        )
        why = "naive casefold dict silently dropped a case-distinct sibling"
    elif shape_id == "d-non-ascii":
        ok = result.count < oracle_count
        why = "naive ASCII encode skipped non-ASCII names"
    elif shape_id == "e-spaces":
        spaced = [
            p.relative_to(root).as_posix()
            for p in iter_files(root)
            if " " in p.relative_to(root).as_posix()
        ]
        intact = [s for s in spaced if s in result.archive_members]
        ok = len(spaced) > 0 and len(intact) == 0
        why = "naive split-on-space did not preserve spaced paths as members"
    elif shape_id == "f-trailing-dot-space":
        ok = result.count < oracle_count and len(result.collisions) >= 1
        why = "naive trailing-dot/space strip collided distinct names"
    else:
        ok, why = False, f"unknown shape {shape_id}"
    return ok, why, result


def hardened_passes_shape(
    shape_id: str, root: Path, oracle_count: int
) -> tuple[bool, str, WalkResult]:
    result = hardened_walk(root)
    if result.swallowed_to_zero:
        return False, "hardened swallowed a crash to count 0", result
    if result.count != oracle_count:
        return (
            False,
            f"hardened count {result.count} != oracle {oracle_count}",
            result,
        )
    if shape_id == "c-case-collision":
        case_hits = [c for c in result.collisions if c.get("kind") == "case"]
        if not case_hits:
            return False, "hardened did not report the case collision", result
    if shape_id == "f-trailing-dot-space":
        strip_hits = [
            c for c in result.collisions if c.get("kind") == "trailing-strip"
        ]
        if not strip_hits:
            return False, "hardened did not report trailing-strip collision", result
    if shape_id == "e-spaces":
        spaced = [
            p.relative_to(root).as_posix()
            for p in iter_files(root)
            if " " in p.relative_to(root).as_posix()
        ]
        missing = [s for s in spaced if s not in result.archive_members]
        if missing:
            return False, f"hardened zip missing spaced members {missing}", result
    if shape_id == "d-non-ascii":
        non_ascii = [
            p.relative_to(root).as_posix()
            for p in iter_files(root)
            if any(ord(c) > 127 for c in p.relative_to(root).as_posix())
        ]
        missing = [s for s in non_ascii if s not in result.files]
        if missing:
            return False, f"hardened dropped non-ASCII {missing}", result
    if result.crashed:
        return False, f"hardened crashed: {result.error}", result
    return True, "hardened counted every oracle file and did not swallow", result
