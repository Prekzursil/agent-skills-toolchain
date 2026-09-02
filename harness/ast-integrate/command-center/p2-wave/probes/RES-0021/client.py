#!/usr/bin/env python3
"""Locate the live installed CLI client on this Linux worktree."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CLAUDE_CANDIDATES = (
    "claude",
    str(Path.home() / ".local/bin/claude"),
    "/usr/local/bin/claude",
    "/usr/bin/claude",
)
AGENT_CANDIDATES = (
    os.environ.get("CURSOR_AGENT_BIN") or "",
    "/root/.local/bin/agent",
    "/root/.local/bin/cursor-agent",
    str(Path.home() / ".local/bin/agent"),
    str(Path.home() / ".local/bin/cursor-agent"),
    "/usr/local/bin/agent",
    "/usr/local/bin/cursor-agent",
)


def _existing_file(path: str) -> Path | None:
    if not path:
        return None
    p = Path(path).expanduser()
    if p.is_file():
        return p.resolve()
    found = shutil.which(path)
    if found:
        return Path(found).resolve()
    return None


def _is_windows_interop_shim(path: Path) -> bool:
    """A tiny WSL shim that execs a Windows .exe is not a local Linux client.

    Its wrapper behaviour (env exports, bundled node) belongs to the Windows
    install on the other side of the interop boundary, so probing it here
    measures nothing about the Linux client surface.
    """
    try:
        if path.stat().st_size > 512:
            return False
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "/mnt/" in text and ".exe" in text


def find_claude() -> Path | None:
    for c in CLAUDE_CANDIDATES:
        got = _existing_file(c)
        if got and not _is_windows_interop_shim(got):
            return got
    return None


def _runnable_agent(path: Path) -> bool:
    parent = path.resolve().parent
    node = parent / "node"
    return (parent / "index.js").is_file() and (node.is_file() or node.is_symlink())


def find_cursor_agent() -> Path | None:
    versions = Path.home() / ".local/share/cursor-agent/versions"
    if versions.is_dir():
        kids = sorted((p for p in versions.iterdir() if p.is_dir()), reverse=True)
        for kid in kids:
            for name in ("cursor-agent", "agent"):
                cand = kid / name
                if cand.is_file() and _runnable_agent(cand):
                    return cand.resolve()
    for c in AGENT_CANDIDATES:
        got = _existing_file(c)
        if got and _runnable_agent(got):
            return got
    for name in ("agent", "cursor-agent"):
        got = _existing_file(name)
        if got:
            return got
    return None


def wrapper_dir(launcher: Path) -> Path:
    try:
        return launcher.resolve().parent
    except OSError:
        return launcher.parent


def bundled_index(launcher: Path) -> Path | None:
    idx = wrapper_dir(launcher) / "index.js"
    if idx.is_file():
        return idx
    # ~/.local/bin/agent is a copy that points at sibling node/index.js
    # versioned installs live under ~/.local/share/cursor-agent/versions/*
    versions = Path.home() / ".local/share/cursor-agent/versions"
    if versions.is_dir():
        kids = sorted((p for p in versions.iterdir() if p.is_dir()), reverse=True)
        for kid in kids:
            cand = kid / "index.js"
            if cand.is_file():
                return cand
    return None


def bundled_node(launcher: Path) -> Path | None:
    node = wrapper_dir(launcher) / "node"
    if node.is_file():
        return node
    idx = bundled_index(launcher)
    if idx:
        node = idx.parent / "node"
        if node.is_file():
            return node
    return None


def describe_client() -> dict:
    claude = find_claude()
    agent = find_cursor_agent()
    if claude is not None:
        live = claude
        family = "claude-code"
        catalog_match = True
    elif agent is not None:
        live = agent
        family = "cursor-agent"
        catalog_match = False
    else:
        return {
            "present": False,
            "family": None,
            "path": None,
            "catalog_target": "claude-code",
            "catalog_match": False,
            "note": "neither claude nor cursor-agent found on PATH",
        }
    idx = bundled_index(live)
    node = bundled_node(live)
    return {
        "present": True,
        "family": family,
        "path": str(live),
        "launcher": str(live),
        "index_js": str(idx) if idx else None,
        "bundled_node": str(node) if node else None,
        "catalog_target": "claude-code",
        "catalog_match": catalog_match,
        "claude_path": str(claude) if claude else None,
        "note": (
            "Catalog RES-0021 names the Claude Code client. "
            "This Linux worktree has no `claude` binary; "
            "the live installed client this program's P2 dispatcher execs is Cursor agent."
            if family == "cursor-agent"
            else "Live Claude Code binary found."
        ),
    }
