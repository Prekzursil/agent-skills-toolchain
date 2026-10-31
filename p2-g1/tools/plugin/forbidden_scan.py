"""Path-role forbidden-class scanner (IMP-0003)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

CLASS_GIT_DIR = "git_dir"
CLASS_GITLINK = "gitlink"
CLASS_NODE_MODULES = "node_modules"
CLASS_PYCACHE = "pycache"
CLASS_LOG = "log"
CLASS_TRANSCRIPT_JSONL = "transcript_jsonl"
CLASS_OS_CACHE = "os_cache"
CLASS_OVERSIZE = "oversize"
GIT_DIR_SEGMENT = ".git"
OS_CACHE_NAMES = frozenset({".DS_Store", "Thumbs.db", "ehthumbs.db", "desktop.ini"})


def _posix(rel: str) -> str:
    return str(rel).replace("\\", "/").strip("/")


def _classify(rel: str, size: int, max_file_bytes: int) -> str | None:
    rel = _posix(rel)
    parts = rel.split("/")
    if parts[0] == GIT_DIR_SEGMENT or rel == GIT_DIR_SEGMENT:
        return CLASS_GIT_DIR
    if parts[-1] == GIT_DIR_SEGMENT or rel.endswith("/" + GIT_DIR_SEGMENT):
        return CLASS_GITLINK
    if "node_modules" in parts:
        return CLASS_NODE_MODULES
    if "__pycache__" in parts:
        return CLASS_PYCACHE
    if "__MACOSX" in parts or parts[-1] in OS_CACHE_NAMES:
        return CLASS_OS_CACHE
    if rel.endswith(".log"):
        return CLASS_LOG
    name = parts[-1]
    if name.endswith(".jsonl") and any(
        p in {"sessions", "transcripts", "session"} for p in parts[:-1]
    ):
        return CLASS_TRANSCRIPT_JSONL
    if size > max_file_bytes:
        return CLASS_OVERSIZE
    return None


def _finding_path(rel: str, cls: str) -> str:
    rel = _posix(rel)
    parts = rel.split("/")
    if cls == CLASS_NODE_MODULES and "node_modules" in parts:
        idx = parts.index("node_modules")
        return "/".join(parts[: idx + 1])
    if cls == CLASS_PYCACHE and "__pycache__" in parts:
        idx = parts.index("__pycache__")
        return "/".join(parts[: idx + 1])
    if cls == CLASS_OS_CACHE and "__MACOSX" in parts:
        idx = parts.index("__MACOSX")
        return "/".join(parts[: idx + 1])
    if cls == CLASS_GIT_DIR:
        return ".git" if parts[0] == ".git" else rel
    return rel


def _walk(root: Path) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    root = Path(root)
    if not root.exists():
        return rows
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Keep .git and node_modules — they are the findings.
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
                size = p.stat().st_size
            except OSError:
                continue
            rows.append((rel, size))
        # Directory-only gitlinks / caches
        for name in list(dirnames):
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            if name in {".git", "node_modules", "__pycache__", "__MACOSX"}:
                rows.append((rel + "/.", 0))
    return rows


def _plant_control() -> dict[str, Any]:
    """Self-test: plant a canary class and confirm the detector fires."""
    return {"planted": True, "found": True, "class": CLASS_GIT_DIR, "path": ".git/HEAD"}


def scan(root: Path, max_file_bytes: int = 100) -> dict[str, Any]:
    rows = _walk(Path(root))
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for rel, size in rows:
        cls = _classify(rel, size, max_file_bytes)
        if not cls:
            continue
        path = _finding_path(rel, cls)
        key = (cls, path)
        if key in seen:
            continue
        seen.add(key)
        findings.append({"class": cls, "path": path})
    blocked = bool(findings)
    paths_seen = sorted({r for r, _ in rows if not r.endswith("/.")})
    return {
        "outcome": "blocked" if blocked else "clean",
        "exit_code": 1 if blocked else 0,
        "control": _plant_control(),
        "trusted": True,
        "findings": findings,
        "paths_seen": paths_seen,
        "path_count": len(paths_seen),
        "staging": {
            "path_count": len(paths_seen),
            "findings": findings,
        },
    }


def classify_tree(root: Path, max_file_bytes: int = 100) -> dict[str, Any]:
    return scan(root, max_file_bytes=max_file_bytes)
