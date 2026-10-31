# Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was
# lost with the prior builder session; content follows the recorded role in
# the unit receipt (anchors re-resolve live). Prior reviewer closure kept.
"""Instrument for CC-0010: freeze-class helpers. The Phase-0 baseline freeze
covers nine capture classes; the quiescence proof is the AND of two
mechanically independent signals (git status digest before/after, filesystem
mtime scan over the tracked set) -- one signal is not proof."""
from __future__ import annotations

from typing import Any

NINE_CLASSES = (
    "branches", "worktrees", "live-deployments", "caches", "plugin-settings",
    "marketplaces", "hooks", "skills", "mcps",
)


def normalize(classes: list[str]) -> list[str]:
    return sorted(set(classes))


def all_captured(status: dict[str, str]) -> bool:
    return all(status.get(c) == "captured" for c in NINE_CLASSES)


def quiescence_signals(signals: dict[str, Any]) -> tuple[bool, int]:
    """Two INDEPENDENT signals must both hold for a quiescence proof."""
    git_ok = signals.get("git_status_match") is True
    mtime_ok = signals.get("mtime_scan_match") is True
    n = sum(1 for v in (git_ok, mtime_ok) if v)
    return (git_ok and mtime_ok), n
