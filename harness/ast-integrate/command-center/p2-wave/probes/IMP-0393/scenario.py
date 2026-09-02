#!/usr/bin/env python3
"""Fixture paths and index load for IMP-0393 probes."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
INDEX_PATH = FIXTURES / "capability-index.json"
CWD_WEB = FIXTURES / "cwd-roots" / "web"
CWD_WEB_SRC = CWD_WEB / "src"
CWD_WEB_APP = CWD_WEB / "app"
CWD_WEB_APP_SRC = CWD_WEB_APP / "src"
CWD_OTHER = FIXTURES / "cwd-roots" / "other"
CLAUDE_TREE = FIXTURES / "trees" / "claude-skills"
AGENTS_TREE = FIXTURES / "trees" / "agents-skills"

sys.path.insert(0, str(REPO / "tools" / "router"))
import conflict_resolve as cr  # noqa: E402


def index() -> dict:
    return cr.load_index(INDEX_PATH)


def resolve_at(cwd: Path) -> dict:
    return cr.resolve_index(index(), cwd)
