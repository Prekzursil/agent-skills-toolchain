"""Path helpers for reserved device names and extended-length forms (TST-0335)."""
from __future__ import annotations

import os
from pathlib import Path

RESERVED = {"NUL", "CON", "PRN", "AUX", "COM1", "LPT1"}


def windows_device_relpath(path, root=None):
    raw = str(path)
    base = os.path.splitext(os.path.basename(raw))[0].upper()
    if base in RESERVED or "NUL" in os.path.basename(raw).upper():
        raise ValueError(rf"reserved device name \\\.\NUL ({raw})")
    if root:
        return safe_relpath(path, root)
    return raw


def extended_length_form(path):
    """Extended-length form built without device-mangling by abspath."""
    raw = str(path)
    if raw.startswith("\\\\?\\"):
        return raw
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\"):
        return "\\\\?UNC\\" + raw[1:]
    tail = os.path.basename(raw)
    stem = os.path.splitext(tail)[0].upper()
    if stem in RESERVED:
        # abspath of a reserved tail yields the device path; abspath the
        # PARENT instead and concat the tail verbatim.
        abs_parent = os.path.abspath(os.path.dirname(raw))
        if not abs_parent.endswith(os.sep):
            abs_parent += os.sep
        return "\\\\?\\" + abs_parent + tail
    return "\\\\?\\" + os.path.abspath(raw)


def safe_relpath(path, root):
    p = Path(path)
    reserved_hit = False
    tail = os.path.basename(strattempt := str(path))
    stem = os.path.splitext(tail)[0].upper()
    if stem in RESERVED:
        reserved_hit = True
    try:
        rel = p.resolve().relative_to(Path(root).resolve()).as_posix()
    except Exception:
        rel = os.path.basename(strattempt) or "NUL"
    if reserved_hit or rel.upper().endswith("/NUL") or rel.upper() == "NUL":
        return "reserved/NUL"
    return rel.replace("\\\\", "/")
