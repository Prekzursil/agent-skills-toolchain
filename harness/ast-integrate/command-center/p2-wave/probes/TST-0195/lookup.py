#!/usr/bin/env python3
"""Declared skill-path lookup: exact on Linux, casefold-with-warning on Windows.

A raw ``Path.exists`` call is accidental platform behaviour (silent hit on
NTFS / APFS, miss on ext4). This loader lists each directory and compares
names under an explicit policy so the Skills/ vs skills/ difference is
declared rather than inherited from the host filesystem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

LINUX = "linux"
WINDOWS = "windows"


@dataclass
class LookupResult:
    ok: bool
    platform: str
    requested: str
    resolved: str | None
    warnings: list[str] = field(default_factory=list)
    reason: str = ""
    matched_components: list[str] = field(default_factory=list)

    def names_mismatch(self, requested_part: str, on_disk: str) -> bool:
        blob = " ".join(self.warnings)
        return requested_part in blob and on_disk in blob


def split_ref(requested: str) -> list[str]:
    text = (requested or "").replace("\\", "/").strip()
    if text.startswith("./"):
        text = text[2:]
    text = text.strip("/")
    parts = [p for p in text.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        raise ValueError("parent-segment-refused")
    return parts


def warn_text(requested_part: str, on_disk: str) -> str:
    return f"casing-mismatch requested={requested_part!r} on-disk={on_disk!r}"


def choose(names: Iterable[str], want: str, platform: str) -> tuple[str | None, str | None]:
    listing = list(names)
    if platform == LINUX:
        return (want, None) if want in listing else (None, None)
    if platform != WINDOWS:
        raise ValueError(f"unknown-platform:{platform}")
    folded = want.casefold()
    hits = [n for n in listing if n.casefold() == folded]
    if not hits:
        return None, None
    hits.sort()
    chosen = hits[0]
    if chosen != want:
        return chosen, warn_text(want, chosen)
    return chosen, None


def listdir_names(path: Path) -> list[str]:
    return sorted(p.name for p in path.iterdir())


def lookup(root: Path, requested: str, platform: str) -> LookupResult:
    """Resolve ``requested`` under ``root`` using the declared platform policy."""
    root = Path(root)
    if not root.is_dir():
        return LookupResult(
            ok=False,
            platform=platform,
            requested=requested,
            resolved=None,
            reason="root-not-a-directory",
        )
    try:
        parts = split_ref(requested)
    except ValueError as exc:
        return LookupResult(
            ok=False,
            platform=platform,
            requested=requested,
            resolved=None,
            reason=str(exc),
        )
    if not parts:
        return LookupResult(
            ok=False,
            platform=platform,
            requested=requested,
            resolved=None,
            reason="empty-ref",
        )

    current = root
    actual: list[str] = []
    warnings: list[str] = []
    for i, part in enumerate(parts):
        if not current.is_dir():
            return LookupResult(
                ok=False,
                platform=platform,
                requested=requested,
                resolved=None,
                warnings=warnings,
                reason="not-a-directory",
                matched_components=actual,
            )
        try:
            names = listdir_names(current)
        except OSError as exc:
            return LookupResult(
                ok=False,
                platform=platform,
                requested=requested,
                resolved=None,
                warnings=warnings,
                reason=f"listdir-error:{exc}",
                matched_components=actual,
            )
        chosen, warn = choose(names, part, platform)
        if chosen is None:
            return LookupResult(
                ok=False,
                platform=platform,
                requested=requested,
                resolved=None,
                warnings=warnings,
                reason="exact-miss" if platform == LINUX else "casefold-miss",
                matched_components=actual,
            )
        if warn:
            warnings.append(warn)
        actual.append(chosen)
        current = current / chosen
        last = i == len(parts) - 1
        if last and not current.exists():
            return LookupResult(
                ok=False,
                platform=platform,
                requested=requested,
                resolved=None,
                warnings=warnings,
                reason="missing-after-match",
                matched_components=actual,
            )

    rel = "/".join(actual)
    return LookupResult(
        ok=True,
        platform=platform,
        requested=requested,
        resolved=rel,
        warnings=warnings,
        reason="ok-silent" if not warnings else "ok-with-warning",
        matched_components=actual,
    )


def live_os_exists(root: Path, requested: str) -> bool:
    """Accidental host filesystem lookup (Path.exists). Independent of policy."""
    parts = split_ref(requested)
    return Path(root).joinpath(*parts).exists()


def silent_windows_lookup(root: Path, requested: str) -> LookupResult:
    """Mutant: Windows casefold with the warning stream discarded.

    Contract must reject this: a silent hit is the accidental NTFS behaviour
    the unit exists to distinguish from a declared warning.
    """
    result = lookup(root, requested, WINDOWS)
    return LookupResult(
        ok=result.ok,
        platform="windows-silent-mutant",
        requested=result.requested,
        resolved=result.resolved,
        warnings=[],
        reason="silent-ok" if result.ok else result.reason,
        matched_components=result.matched_components,
    )


def contract_mismatch(
    linux: LookupResult,
    windows: LookupResult,
    *,
    requested_part: str = "Skills",
    on_disk: str = "skills",
) -> tuple[bool, str]:
    """PASS: Linux exact-miss; Windows miss OR hit with warning naming both spellings."""
    if linux.ok:
        return False, "linux-mismatch-must-fail"
    if linux.reason != "exact-miss":
        return False, f"linux-reason:{linux.reason}"
    if not windows.ok:
        return True, "windows-same-failure"
    if not windows.warnings:
        return False, "windows-hit-without-warning"
    if not windows.names_mismatch(requested_part, on_disk):
        return False, "windows-warning-omits-names"
    return True, "windows-hit-with-named-warning"


def contract_exact(linux: LookupResult, windows: LookupResult) -> tuple[bool, str]:
    """PASS: correctly-cased refs resolve silently on both legs."""
    if not linux.ok or linux.warnings:
        return False, f"linux-exact:{linux.reason}:{linux.warnings}"
    if not windows.ok or windows.warnings:
        return False, f"windows-exact:{windows.reason}:{windows.warnings}"
    if linux.resolved != windows.resolved:
        return False, "exact-resolved-disagree"
    return True, "both-silent"
