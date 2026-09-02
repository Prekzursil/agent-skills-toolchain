"""Import the foundry library from this worktree."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def repo() -> Path:
    return REPO


def ensure_import() -> None:
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
