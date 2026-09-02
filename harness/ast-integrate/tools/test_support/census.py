"""Adoption census for the both-states fixture."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "ovh-monitor",
    "error-pull",
}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def scan_tree(root: Path, repo: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    repo = Path(repo) if repo is not None else root
    users: list[str] = []
    hands: list[str] = []
    for dirpath, dirnames, filenames in os_walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = Path(dirpath) / name
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = _rel(path, repo)
            uses_fixture = (
                "from tools.test_support.both_states import" in text
                or "import tools.test_support.both_states" in text
            )
            hand = (
                ("def both_states(" in text or "def both_states():" in text)
                and "tools.test_support.both_states" not in text
            )
            if uses_fixture:
                users.append(rel)
            if hand:
                hands.append(rel)
    return {
        "fixture_users": sorted(set(users)),
        "hand_rolled": sorted(set(hands)),
    }


def os_walk(root: Path):
    import os

    return os.walk(root, followlinks=False)


def census(repo: Path) -> dict[str, Any]:
    repo = Path(repo)
    live = scan_tree(repo, repo=repo)
    registry_path = repo / "command-center" / "TEST-REGISTRY.json"
    present = registry_path.is_file()
    parseable = False
    if present:
        try:
            json.loads(registry_path.read_text(encoding="utf-8"))
            parseable = True
        except (OSError, json.JSONDecodeError):
            parseable = False
    users = live["fixture_users"]
    hands = live["hand_rolled"]
    return {
        "live": live,
        "adoption": {
            "live_fixture_users": len(users),
            "live_hand_rolled": len(hands),
            "registry_present": present,
        },
        "registry": {"present": present, "parseable": parseable, "path": str(registry_path)},
    }
