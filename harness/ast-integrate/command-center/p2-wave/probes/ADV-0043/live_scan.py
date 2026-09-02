#!/usr/bin/env python3
"""Scan the host for a live MCP Agent Mail persistence store.

Does not modify any found identity or token. Read-only.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

CANDIDATE_DIRS = (
    Path.home() / ".mcp_agent_mail_git_mailbox_repo",
    Path.home() / ".agent_mail",
    Path.home() / ".agent-mail",
    Path("/var/lib/mcp_agent_mail"),
    Path("/opt/p2/ast-integrate/.agent-mail"),
    Path("/opt/p2/ast-integrate/.mcp_agent_mail"),
)
ENV_KEYS = (
    "STORAGE_ROOT",
    "MCP_AGENT_MAIL_STORAGE",
    "AGENT_MAIL_HOME",
)


def _iter_sqlite(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file() and root.suffix in {".db", ".sqlite", ".sqlite3"}:
        return [root]
    found: list[Path] = []
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
        for name in filenames:
            if name.endswith((".db", ".sqlite", ".sqlite3")):
                found.append(Path(dirpath) / name)
        if len(found) > 24:
            break
    return found


def _probe_sqlite(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "readable": False,
        "tables": [],
        "message_rows": None,
        "agent_rows": None,
        "error": None,
    }
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
        try:
            cur = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1"
            )
            tables = [r[0] for r in cur.fetchall()]
            info["tables"] = tables
            info["readable"] = True
            lower = {t.lower(): t for t in tables}
            for cand in ("messages", "message", "mail", "inbox"):
                if cand in lower:
                    n = con.execute(
                        f'SELECT COUNT(*) FROM "{lower[cand]}"'
                    ).fetchone()[0]
                    info["message_rows"] = int(n)
                    break
            for cand in ("agents", "agent", "identities"):
                if cand in lower:
                    n = con.execute(
                        f'SELECT COUNT(*) FROM "{lower[cand]}"'
                    ).fetchone()[0]
                    info["agent_rows"] = int(n)
                    break
        finally:
            con.close()
    except (sqlite3.Error, OSError) as exc:
        info["error"] = type(exc).__name__
    return info


def scan_live_store() -> dict[str, Any]:
    roots: list[str] = []
    for key in ENV_KEYS:
        val = os.environ.get(key)
        if val:
            roots.append(val)
    for path in CANDIDATE_DIRS:
        roots.append(str(path))
    seen: set[str] = set()
    sqlite_hits: list[dict[str, Any]] = []
    existing_roots: list[str] = []
    for raw in roots:
        if raw in seen:
            continue
        seen.add(raw)
        root = Path(raw)
        if root.exists():
            existing_roots.append(raw)
        for db in _iter_sqlite(root):
            sqlite_hits.append(_probe_sqlite(db))
    return {
        "live_store_present": bool(sqlite_hits) or bool(existing_roots),
        "existing_roots": existing_roots,
        "sqlite_hits": sqlite_hits,
        "note": (
            "Read-only scan. No live identity was registered, mutated, "
            "or retired. Absence means this host has no local Agent Mail "
            "persistence; the isolated replica still measures the published "
            "tool contract."
        ),
    }
