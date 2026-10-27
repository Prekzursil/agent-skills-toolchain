"""Loader lookup policy (TST-0195): casing is exact on Linux, normalized-with-warning on Windows.

The platform difference is DECLARED here, not inherited from Path.exists:
  * linux  policy: every path component must match an on-disk name exactly
                   (case-sensitive string comparison against the live directory
                   listing); any casing mismatch is an exact-miss.
  * windows policy: components match case-insensitively; a component that only
                   matches after casefolding resolves, but emits a warning that
                   names both spellings. An exact match is silent.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

__all__ = ("lookup",)


def _match_component(directory: Path, component: str, platform: str) -> tuple[str | None, list[str]]:
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return None, []
    if component in names:
        return component, []
    if platform == "windows":
        folded = component.casefold()
        for name in names:
            if name.casefold() == folded:
                warn = f"casing-mismatch requested='{component}' on-disk='{name}'"
                return name, [warn]
    return None, []


def lookup(requested: str, root: Path | str, platform: str) -> dict[str, Any]:
    """Resolve ``requested`` (a ./-relative slash path) under ``root`` per platform policy."""
    platform = str(platform).lower()
    root = Path(root)
    parts = [p for p in str(requested).replace("\\", "/").split("/") if p not in ("", ".")]
    warnings: list[str] = []
    matched: list[str] = []
    current = root
    for part in parts:
        name, warns = _match_component(current, part, platform)
        if name is None:
            return {
                "requested": requested,
                "platform": platform,
                "matched_components": matched,
                "resolved": None,
                "ok": False,
                "reason": "exact-miss" if platform == "linux" else "no-match",
                "warnings": list(warnings),
            }
        warnings.extend(warns)
        matched.append(name)
        current = current / name
    reason = "ok-silent"
    if platform == "windows" and warnings:
        reason = "ok-with-warning"
    return {
        "requested": requested,
        "platform": platform,
        "matched_components": matched,
        "resolved": "/".join(matched) if matched else None,
        "ok": True,
        "reason": reason,
        "warnings": warnings,
    }
