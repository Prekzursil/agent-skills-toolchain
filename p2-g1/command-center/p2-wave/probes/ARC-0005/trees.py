"""Control-tree paths for the ARC-0005 stop-hook probe.

Restored 2026-10-24: the deployed tree lost this module (and detector.py)
while keeping stop_hook.py, which imports `trees.CTRL_LIVE / CTRL_REPO`.
Paths point at the committed control fixtures: a repo-side tree and the
live-side tree it is diffed against.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

CTRL_REPO = HERE / "fixtures" / "control" / "repo"
CTRL_LIVE = HERE / "fixtures" / "control" / "live"

CENSUS_REPO = HERE / "fixtures" / "census" / "repo"
CENSUS_LIVE = HERE / "fixtures" / "census" / "live"
