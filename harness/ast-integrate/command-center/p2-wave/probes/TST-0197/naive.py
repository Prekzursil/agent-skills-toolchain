"""Naive enumerator: the Phase-0 pattern that zeros counts on reserved names.

Windows collapses a reserved basename to `\\\\.\\NAME`. `ntpath.relpath`
then raises ValueError. A broad `except Exception: return []` turns that
crash into a silent zero — the detector-failure this unit exists to catch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import ntpath

from enumerator import RESERVED_BASENAMES, device_namespace_path, is_reserved_device_name


def naive_ntpath_walk_raising(root: Path, start: str = r"C:\worktree") -> dict[str, Any]:
    """os.walk + ntpath.relpath on the device-namespace form. Raises on NUL."""
    rels: list[str] = []
    try:
        for dirpath, _dirnames, filenames in __import__("os").walk(root):
            for name in filenames:
                if is_reserved_device_name(name):
                    collapsed = device_namespace_path(name)
                else:
                    collapsed = ntpath.join(start, name)
                rels.append(ntpath.relpath(collapsed, start))
        return {
            "raised": None,
            "count": len(rels),
            "rels": rels,
            "swallowed": False,
        }
    except ValueError as exc:
        return {
            "raised": f"{type(exc).__name__}: {exc}",
            "count": None,
            "rels": rels,
            "swallowed": False,
            "partial_before_raise": len(rels),
        }


def naive_ntpath_walk_swallowed(root: Path, start: str = r"C:\worktree") -> dict[str, Any]:
    """Same walk, but a broad except returns []. This is the silent-zero bug."""
    try:
        result = naive_ntpath_walk_raising(root, start=start)
        if result.get("raised"):
            return {
                "count": 0,
                "rels": [],
                "swallowed": True,
                "swallowed_error": result["raised"],
                "complete_claimed": True,
            }
        return {
            "count": result["count"],
            "rels": result["rels"],
            "swallowed": False,
            "swallowed_error": None,
            "complete_claimed": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "count": 0,
            "rels": [],
            "swallowed": True,
            "swallowed_error": f"{type(exc).__name__}: {exc}",
            "complete_claimed": True,
        }


def reserved_set() -> tuple[str, ...]:
    return RESERVED_BASENAMES
