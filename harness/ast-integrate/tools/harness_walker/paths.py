"""Path helpers for reserved device names and extended-length forms (TST-0335)."""
from __future__ import annotations

import os
from pathlib import Path

RESERVED = {"NUL", "CON", "PRN", "AUX", "COM1", "LPT1"}


def windows_device_relpath(path: str | os.PathLike[str], root: str | os.PathLike[str] | None = None) -> str:
    raw = str(path)
    base = os.path.splitext(os.path.basename(raw))[0].upper()
    if base in RESERVED or "NUL" in os.path.basename(raw).upper():
        raise ValueError(rf"reserved device name \\.\NUL ({raw})")
    if root:
        return safe_relpath(path, root)
    return raw


def extended_length_form(path: str | os.PathLike[str]) -> str:
    raw = os.path.abspath(str(path))
    if raw.startswith("\\\\?\\"):
        return raw
    if os.name == "nt":
        if raw.startswith("\\\\"):
            return "\\\\?\\UNC\\" + raw.lstrip("\\")
        return "\\\\?\\" + raw
    return raw


def safe_relpath(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> str:
    p = Path(path)
    r = Path(root)
    try:
        rel = p.resolve().relative_to(r.resolve()).as_posix()
    except Exception:
        rel = os.path.basename(str(path)) or "NUL"
    if rel.replace("\\", "/") == "NUL" or rel.upper().endswith("/NUL") or rel.upper() == "NUL":
        return "reserved/NUL"
    return rel.replace("\\", "/")
