"""Windows extended-length prefix and reserved-device-name helpers.

The Phase-0 enumerator crashed with:
    ValueError: path is on mount '\\\\.\\NUL'
because ntpath.relpath treats the device mount ``\\\\.\\NUL`` as a different
drive from the walk root. The extended-length form ``\\\\?\\C:\\...\\NUL``
with a matching prefixed start is the documented recovery; this module
exercises that conversion rather than assuming it is present in callers.
"""
from __future__ import annotations

import ntpath
import re
from typing import Iterable

RESERVED_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(1, 10)}, *{f"LPT{i}" for i in range(1, 10)}}
)
_PREFIX_DRIVE = "\\\\?\\"
_PREFIX_UNC = "\\\\?\\UNC\\"
_COUNTER = {"n": 0}


def reset_prefix_counter() -> None:
    _COUNTER["n"] = 0


def prefix_invocation_count() -> int:
    return _COUNTER["n"]


def _stem(name: str) -> str:
    base = name.split("\\")[-1].split("/")[-1]
    if not base:
        return ""
    return base.split(".")[0].upper()


def is_reserved_component(name: str) -> bool:
    return _stem(name) in RESERVED_STEMS


def needs_extended_length(path: str, *, limit: int = 260) -> bool:
    if len(path) > limit:
        return True
    for part in re.split(r"[\\/]", path.replace("/", "\\")):
        if part and is_reserved_component(part):
            return True
    return False


def to_extended_length(path: str) -> str:
    """Return a ``\\\\?\\``-prefixed Windows path. Always counted (exercised)."""
    _COUNTER["n"] += 1
    p = path.replace("/", "\\")
    if p.startswith(_PREFIX_DRIVE) or p.startswith(_PREFIX_UNC):
        return p
    if p.startswith("\\\\.\\") and not p.upper().startswith("\\\\.\\C:"):
        # Device-mount form (\\\\.\\NUL). Caller must not feed this to relpath;
        # keep it recognisable rather than inventing a drive.
        return p
    if p.startswith("\\\\"):
        rest = p[2:]
        return _PREFIX_UNC + rest
    if len(p) >= 2 and p[1] == ":":
        return _PREFIX_DRIVE + p
    return _PREFIX_DRIVE + p


def is_device_mount(path: str) -> bool:
    p = path.replace("/", "\\")
    return p.startswith("\\\\.\\") and not p.upper().startswith("\\\\.\\C:")


def naive_nt_relpath(path: str, start: str) -> str:
    """The crashing primitive: ntpath.relpath with no prefix."""
    return ntpath.relpath(path, start)


def safe_nt_relpath(path: str, start: str) -> str:
    """Prefix both sides, then relpath. Device-mount paths fail closed."""
    if is_device_mount(path) or is_device_mount(start):
        raise ValueError(
            f"explicit-refuse device-mount relpath path={path!r} start={start!r}"
        )
    return ntpath.relpath(to_extended_length(path), to_extended_length(start))


def windows_join(root: str, rel_parts: Iterable[str]) -> str:
    p = root.replace("/", "\\")
    for part in rel_parts:
        p = ntpath.join(p, part.replace("/", "\\"))
    return p
