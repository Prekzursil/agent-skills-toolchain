#!/usr/bin/env python3
"""Independent recomputation of the IMP-0085 compatibility filter.

Mechanically different from tools/marketplace/compat.py: set-subtraction over
raw metadata instead of per-candidate sequential evaluation. Used as signal 2.
Does not import compat.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

_ALIASES = {
    "windows": "windows",
    "win32": "windows",
    "win64": "windows",
    "win": "windows",
    "cygwin": "windows",
    "macos": "macos",
    "darwin": "macos",
    "osx": "macos",
    "mac": "macos",
    "linux": "linux",
    "linux2": "linux",
}
_KEYS = (
    "platforms",
    "min_client_version",
    "max_client_version",
    "supported_clients",
)
_VER = re.compile(
    r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def _key(pkg: Mapping[str, Any]) -> str:
    return f"{pkg['id']}@{pkg['version']}"


def _plat(raw: str) -> str | None:
    return _ALIASES.get(str(raw or "").strip().lower())


def _ver(raw: str) -> tuple | None:
    m = _VER.match(str(raw or "").strip())
    if not m:
        return None
    major, minor, patch, pre = m.group(1), m.group(2), m.group(3), m.group(4)
    core = (int(major), int(minor), int(patch or 0))
    if not pre:
        return (*core, 1, ())
    parts: list[tuple[int, str]] = []
    for bit in pre.split("."):
        if bit.isdigit():
            parts.append((0, f"{int(bit):020d}"))
        else:
            parts.append((1, bit))
    return (*core, 0, tuple(parts))


def _declares(pkg: Mapping[str, Any]) -> dict[str, Any] | None:
    blob = pkg.get("compatibility")
    if not isinstance(blob, dict):
        return None
    if not any(k in blob for k in _KEYS):
        return None
    return blob


def independent_accepted(
    packages: Sequence[Mapping[str, Any]],
    *,
    platform: str,
    client_version: str,
    client_name: str | None = None,
) -> tuple[str, ...]:
    """Set-algebra filter. Unknown packages are subtracted first (conservative)."""
    req_p = _plat(platform)
    req_v = _ver(client_version)
    universe = {_key(p): p for p in packages}
    if req_p is None or req_v is None:
        return ()

    unknown = {k for k, p in universe.items() if _declares(p) is None}
    known = set(universe) - unknown

    plat_bad: set[str] = set()
    for k in known:
        decl = _declares(universe[k]) or {}
        plats = decl.get("platforms")
        if plats is None:
            continue
        if not isinstance(plats, list):
            plat_bad.add(k)
            continue
        allowed = {_plat(str(x)) for x in plats}
        allowed.discard(None)
        if req_p not in allowed:
            plat_bad.add(k)

    name_bad: set[str] = set()
    if client_name is not None:
        got = client_name.strip().lower()
        for k in known - plat_bad:
            decl = _declares(universe[k]) or {}
            names = decl.get("supported_clients")
            if names is None:
                continue
            if not isinstance(names, list):
                name_bad.add(k)
                continue
            bag = {str(s).strip().lower() for s in names if str(s).strip()}
            if got not in bag:
                name_bad.add(k)

    ver_bad: set[str] = set()
    for k in known - plat_bad - name_bad:
        decl = _declares(universe[k]) or {}
        min_raw = decl.get("min_client_version")
        if min_raw is not None:
            mv = _ver(str(min_raw))
            if mv is None or req_v < mv:
                ver_bad.add(k)
                continue
        max_raw = decl.get("max_client_version")
        if max_raw is not None:
            xv = _ver(str(max_raw))
            if xv is None or req_v > xv:
                ver_bad.add(k)

    kept = known - plat_bad - name_bad - ver_bad
    return tuple(sorted(kept))


def load_packages(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("packages") or data.get("plugins") or []
    return [p for p in rows if isinstance(p, dict)]
