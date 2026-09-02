#!/usr/bin/env python3
"""Artifact writer that preflights resolved path length before any byte is written.

TST-0201 contract: the full resolved destination is measured, a budget breach
is refused, and the refusal creates zero entries under the target root.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Mapping

DEFAULT_BUDGET = 260  # Win32 MAX_PATH: character count of the resolved path
NAME_MAX = 255


def resolved_str(path: Path | str) -> str:
    """Resolved path string without creating anything.

    Existing prefix components are realpath'd (follows symlinks). A missing
    suffix is normalized and appended. Never mkdir/open.
    """
    abs_p = os.path.abspath(os.fspath(path))
    missing: list[str] = []
    cur = abs_p
    while True:
        if os.path.lexists(cur):
            real = os.path.realpath(cur)
            if missing:
                return os.path.normpath(os.path.join(real, *reversed(missing)))
            return real
        parent, name = os.path.split(cur)
        if name:
            missing.append(name)
        if parent == cur:
            return os.path.normpath(abs_p)
        cur = parent


def resolved_len(path: Path | str) -> int:
    return len(resolved_str(path))


def relative_for_length(root: Path | str, total: int) -> str:
    """Relative path under root whose resolved length is exactly `total`."""
    base = resolved_str(root)
    need = total - len(base) - len(os.sep)
    if need < 1:
        raise ValueError(
            f"cannot reach resolved length {total} under {base!r} (len={len(base)})"
        )
    if need <= NAME_MAX:
        rel = "f" * need
    else:
        parts: list[str] = []
        remaining = need
        while remaining > NAME_MAX:
            chunk = min(NAME_MAX, remaining - 2)
            if chunk < 1:
                raise ValueError(f"cannot nest remaining={remaining}")
            parts.append("d" * chunk)
            remaining -= chunk + 1
        if remaining < 1 or remaining > NAME_MAX:
            raise ValueError(f"final component remaining={remaining}")
        parts.append("f" * remaining)
        rel = "/".join(parts)
        if len(rel) != need:
            raise AssertionError(f"nested rel len {len(rel)} != need {need}")
    got = resolved_str(os.path.join(base, rel.replace("/", os.sep)))
    if len(got) != total:
        raise AssertionError(
            f"planned length {total} got {len(got)} base={base!r} rel={rel!r}"
        )
    return rel.replace("\\", "/")


def entries_under(root: Path | str) -> list[str]:
    """Independent filesystem listing of created names under root (files and dirs)."""
    root_p = Path(root)
    if not root_p.exists():
        return []
    found: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root_p):
        for name in list(dirnames) + list(filenames):
            full = Path(dirpath) / name
            found.add(str(full.relative_to(root_p)).replace("\\", "/"))
    return sorted(found)


def _normalize_rel(rel: str) -> str:
    rel = rel.replace("\\", "/").lstrip("/")
    parts = Path(rel).parts
    if not rel or rel.startswith("/") or ".." in parts:
        raise ValueError(f"unsafe relative path: {rel!r}")
    return rel


@dataclass
class MemberPlan:
    rel: str
    resolved: str
    length: int
    size: int
    over_budget: bool


@dataclass
class WriteResult:
    ok: bool
    preflight_rejected: bool
    budget: int
    dest_root: str
    members: list[MemberPlan] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    bytes_written: int = 0
    mkdir_calls: int = 0
    open_calls: int = 0
    message: str = ""
    first_breach: str | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        return d


def plan_members(
    dest_root: Path | str, members: Mapping[str, bytes], budget: int
) -> list[MemberPlan]:
    dest_root = Path(dest_root)
    planned: list[MemberPlan] = []
    for rel, data in members.items():
        rel_n = _normalize_rel(rel)
        resolved = resolved_str(dest_root / rel_n)
        length = len(resolved)
        planned.append(
            MemberPlan(
                rel=rel_n,
                resolved=resolved,
                length=length,
                size=len(data),
                over_budget=length > budget,
            )
        )
    return planned


def write_package(
    dest_root: Path | str,
    members: Mapping[str, bytes],
    *,
    budget: int = DEFAULT_BUDGET,
) -> WriteResult:
    """Write every member, or none.

    The resolved path of every member is checked against `budget` before any
    mkdir/open. One breach rejects the whole package and leaves the dest tree
    untouched.
    """
    dest_root = Path(dest_root)
    planned = plan_members(dest_root, members, budget)
    dest_display = (
        resolved_str(dest_root) if dest_root.exists() else os.path.abspath(str(dest_root))
    )
    result = WriteResult(
        ok=False,
        preflight_rejected=False,
        budget=budget,
        dest_root=dest_display,
        members=planned,
    )
    breaches = [m for m in planned if m.over_budget]
    if breaches:
        first = min(breaches, key=lambda m: m.rel)
        result.preflight_rejected = True
        result.first_breach = first.resolved
        result.message = (
            f"path-length budget exceeded: resolved_len={first.length} "
            f"budget={budget} path={first.resolved}"
        )
        return result

    payload = {_normalize_rel(k): v for k, v in members.items()}
    if not dest_root.exists():
        result.mkdir_calls += 1
        dest_root.mkdir(parents=True, exist_ok=False)

    for rel, data in payload.items():
        dest = dest_root / rel
        parent = dest.parent
        if not parent.exists():
            result.mkdir_calls += 1
            parent.mkdir(parents=True, exist_ok=True)
        result.open_calls += 1
        dest.write_bytes(data)
        result.bytes_written += len(data)
        result.created.append(rel)

    result.ok = True
    result.message = f"wrote {len(result.created)} members bytes={result.bytes_written}"
    return result


def write_package_late_check(
    dest_root: Path | str,
    members: Mapping[str, bytes],
    *,
    budget: int = DEFAULT_BUDGET,
) -> WriteResult:
    """Defective control: write each member, then measure length.

    A mixed in-budget / over-budget package leaves a partial tree. This is the
    detector's known-broken state, not a production path.
    """
    dest_root = Path(dest_root)
    planned = plan_members(dest_root, members, budget)
    result = WriteResult(
        ok=False,
        preflight_rejected=False,
        budget=budget,
        dest_root=os.path.abspath(str(dest_root)),
        members=planned,
        message="late-check writer (defective control)",
    )
    payload = [(_normalize_rel(k), v) for k, v in members.items()]
    dest_root.mkdir(parents=True, exist_ok=True)
    result.mkdir_calls += 1
    for rel, data in payload:
        dest = dest_root / rel
        parent = dest.parent
        if not parent.exists():
            result.mkdir_calls += 1
            parent.mkdir(parents=True, exist_ok=True)
        result.open_calls += 1
        dest.write_bytes(data)
        result.bytes_written += len(data)
        result.created.append(rel)
        length = resolved_len(dest)
        if length > budget:
            result.first_breach = resolved_str(dest)
            result.message = (
                f"late-check: wrote then observed resolved_len={length} "
                f"budget={budget} path={result.first_breach}"
            )
            return result
    result.ok = True
    result.message = f"late-check wrote {len(result.created)} members"
    return result
