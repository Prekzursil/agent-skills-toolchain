"""Discover Prompt One live corpus roots. Absence is reported, not inferred empty."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_ROOT_CANDIDATES = [
    Path.home() / ".claude" / "harness-restore-20260806",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/opt/p2/harness-restore-20260806"),
    REPO / "harness-restore-20260806",
    REPO / "command-center" / "sources" / "harness-restore-20260806",
]

REGISTRY_NAME = "08-WORKFLOW-CANDIDATE-REGISTRY.json"
BLUEPRINT_NAME = "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
ARCHAEOLOGY_NAME = "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md"
# emit.py aliases
REGISTRY_NAME = REGISTRY_NAME
BLUEPRINT_NAME = BLUEPRINT_NAME


def live_roots() -> list[Path]:
    found: list[Path] = []
    for root in LIVE_ROOT_CANDIDATES:
        if root.is_dir() and (root / REGISTRY_NAME).is_file():
            found.append(root)
    return found


def live_status() -> dict:
    roots = live_roots()
    present = []
    for root in roots:
        present.append(
            {
                "root": str(root),
                "registry": (root / REGISTRY_NAME).is_file(),
                "blueprints": (root / BLUEPRINT_NAME).is_file(),
                "archaeology": (root / ARCHAEOLOGY_NAME).is_file(),
            }
        )
    return {
        "present": bool(roots),
        "roots": [str(r) for r in roots],
        "files": present,
        "checked": [str(p) for p in LIVE_ROOT_CANDIDATES],
    }
