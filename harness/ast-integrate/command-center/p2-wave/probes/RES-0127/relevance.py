#!/usr/bin/env python3
"""Research-relevant path predicate for the two-tree partition.

Research units under-count when they read numbered program docs, 05-ECO shards,
and a handful of named indexes from only one tree. This predicate is that set:
top-level .md/.json, numbered NN-* names, 05-ECO*, research/*, and a small
special-name list. It is not a full-tree inventory of 31k files.
"""
from __future__ import annotations

import re
from pathlib import Path

NUMBERED = re.compile(r"^\d{2}-")
SPECIAL = frozenset(
    {
        "_USER-PROMPTS.md",
        "OWNER-DECISIONS.md",
        "32-OWNER-DECISIONS.md",
        "REGISTER.md",
        "CLAIM-REGISTRY.json",
    }
)
SKIP_DIR = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".cache",
        ".venv",
        "venv",
    }
)


def is_research_relevant(rel: str) -> bool:
    rel = rel.replace("\\", "/").lstrip("./")
    if not rel or rel.endswith("/"):
        return False
    parts = rel.split("/")
    if any(p in SKIP_DIR or p.startswith(".") for p in parts[:-1]):
        return False
    name = parts[-1]
    if name.startswith(".") or name.endswith((".pyc", ".pyo")):
        return False
    if name in SPECIAL:
        return True
    if NUMBERED.match(name):
        return True
    if name.startswith("05-ECO"):
        return True
    if parts[0] == "research":
        return name.endswith((".md", ".json", ".txt"))
    if len(parts) == 1 and name.endswith((".md", ".json")):
        return True
    return False


def skip_dir_name(name: str) -> bool:
    return name in SKIP_DIR or name.startswith(".")
