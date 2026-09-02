"""PowerShell Get-Command analogue vs POSIX which.

A .cmd / .bat shim is visible to Get-Command (PATHEXT) and invisible to a
POSIX `which` that only matches the exact basename. This module is the
resolver CNF-0010 requires; it does not shell out to `which`.
"""

from __future__ import annotations

import os
from pathlib import Path

WINDOWS_PATHEXT = (".COM", ".EXE", ".BAT", ".CMD")
LIVE_PATHEXT = ("",) + WINDOWS_PATHEXT


def split_search_path(path_str: str, *, pathsep: str | None = None) -> list[str]:
    sep = pathsep if pathsep is not None else os.pathsep
    return [part for part in path_str.split(sep) if part]


def powershell_resolve(
    name: str,
    path_dirs: list[str],
    *,
    pathext: tuple[str, ...] = LIVE_PATHEXT,
) -> str | None:
    """Resolve `name` the way Get-Command does: PATH order, then PATHEXT.

    Existence of the file is enough. Windows shims are not Unix-executable.
    """
    given = Path(name)
    names: list[str] = [given.name]
    suffix = given.suffix
    if not suffix:
        for ext in pathext:
            if ext and f"{given.name}{ext}" not in names:
                names.append(f"{given.name}{ext}")
    lowered = {n.lower() for n in names}
    for directory in path_dirs:
        try:
            entries = list(Path(directory).iterdir())
        except OSError:
            continue
        by_lower = {p.name.lower(): p for p in entries if p.is_file()}
        for candidate in names:
            hit = by_lower.get(candidate.lower())
            if hit is not None:
                return str(hit.resolve()) if hit.exists() else str(hit)
        # PATHEXT match when the caller passed an extensionless name and the
        # directory listing used a different case (Windows).
        for fname, path in by_lower.items():
            stem, ext = os.path.splitext(fname)
            if stem == given.name.lower() and (
                (not suffix and ext.upper() in {e.upper() for e in pathext if e})
                or fname in lowered
            ):
                return str(path.resolve()) if path.exists() else str(path)
    return None


def posix_which(name: str, path_dirs: list[str]) -> str | None:
    """Git-Bash / POSIX which analogue: exact basename, executable bit required.

    A `ruff.cmd` next to nothing named `ruff` is a miss.
    """
    base = Path(name).name
    for directory in path_dirs:
        path = Path(directory) / base
        try:
            if path.is_file() and os.access(path, os.X_OK):
                return str(path.resolve())
        except OSError:
            continue
    return None


def cmd_shim_control(shim_dir: Path, tool: str = "ruff") -> dict:
    """Both-states fixture: only `{tool}.cmd` exists on PATH."""
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / f"{tool}.cmd"
    shim.write_text("@echo off\r\nrem CNF-0010 PATHEXT shim\r\n", encoding="utf-8")
    # Intentionally do not chmod +x: POSIX which must miss even if the
    # extensionless name were guessed; the name itself is absent.
    dirs = [str(shim_dir)]
    ps = powershell_resolve(tool, dirs, pathext=WINDOWS_PATHEXT)
    posix = posix_which(tool, dirs)
    return {
        "shim_path": str(shim),
        "powershell_resolved": ps,
        "posix_which_resolved": posix,
        "powershell_found_cmd_shim": bool(ps) and ps.lower().endswith(".cmd"),
        "posix_which_missed_cmd_shim": posix is None,
        "shim_basename": tool,
        "pass": bool(ps) and ps.lower().endswith(".cmd") and posix is None,
    }
