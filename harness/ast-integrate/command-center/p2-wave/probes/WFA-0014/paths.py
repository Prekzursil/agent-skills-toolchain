"""Workflow-bearing path classifier for WFA-0014.

Restricted to the surfaces named by WFA-0013/WFA-0014 (committed paths only).
Working-tree existence is never consulted.
"""
from __future__ import annotations

from pathlib import PurePosixPath

PREFIXES = (
    ".github/workflows/",
    "skills/",
    ".agents/skills/",
    ".claude/skills/",
    ".claude/workflows/",
    "rules/",
    "tools/",
    "scripts/",
)
PREFIXES = PREFIXES
EXTS = {".yml", ".yaml", ".md", ".json", ".py", ".sh", ".js", ".toml"}
NAMES = {"skill.md", "agents.md"}
NEEDLES = ("workflow", "orchestrat", "pipeline", "/gates/", "gate-")


def posix(path: str) -> str:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def workflow_bearing(path: str) -> bool:
    p = posix(path)
    if not p or p.endswith("/"):
        return False
    lower = p.lower()
    name = PurePosixPath(p).name.lower()
    if name in NAMES:
        return True
    if any(p == pref.rstrip("/") or p.startswith(pref) for pref in PREFIXES):
        return PurePosixPath(p).suffix.lower() in EXTS or name in NAMES
    if any(n in lower for n in NEEDLES):
        return PurePosixPath(p).suffix.lower() in EXTS
    return False
