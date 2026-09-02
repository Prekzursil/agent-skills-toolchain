"""Locate every .git entry (FILE or directory) under a root.

A submodule presents .git as a FILE whose body starts with `gitdir:`.
A nested (or host) repo presents .git as a directory. Walkers that only
stat directories miss submodules.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def classify_git_entry(path: Path) -> dict:
    if path.is_symlink():
        kind = "symlink"
        form = "unknown"
        gitdir = None
    elif path.is_file():
        kind = "file"
        text = path.read_text(encoding="utf-8", errors="replace")[:4096]
        stripped = text.lstrip()
        if stripped.lower().startswith("gitdir:"):
            form = "submodule-gitfile"
            gitdir = stripped.split(":", 1)[1].strip().splitlines()[0]
        else:
            form = "gitfile-other"
            gitdir = None
    elif path.is_dir():
        kind = "directory"
        form = "git-directory"
        gitdir = None
    else:
        kind = "other"
        form = "unknown"
        gitdir = None
    return {"kind": kind, "form": form, "gitdir": gitdir}


def find_git_os_walk(root: Path, *, exclude_prefixes: Iterable[str] = ()) -> list[dict]:
    """Probe-1 walker: os.walk, prune descent into .git directories, keep .git files."""
    root = root.resolve()
    exclude = tuple(p.strip("/") for p in exclude_prefixes)
    hits: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        rel_dir = Path(dirpath).resolve().relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        skip = False
        for pref in exclude:
            if rel_dir == pref or rel_dir.startswith(pref + "/"):
                skip = True
                break
        if skip:
            dirnames[:] = []
            continue
        if ".git" in dirnames:
            git_path = Path(dirpath) / ".git"
            rel = _rel(root, git_path)
            if not any(rel == p or rel.startswith(p + "/") for p in exclude):
                info = classify_git_entry(git_path)
                hits.append({"path": rel, "method": "os.walk", **info})
            dirnames.remove(".git")
        if ".git" in filenames:
            git_path = Path(dirpath) / ".git"
            rel = _rel(root, git_path)
            if not any(rel == p or rel.startswith(p + "/") for p in exclude):
                info = classify_git_entry(git_path)
                hits.append({"path": rel, "method": "os.walk", **info})
    hits.sort(key=lambda r: r["path"])
    return hits


def find_git_find_cmd(root: Path, *, exclude_prefixes: Iterable[str] = ()) -> list[dict]:
    """Mechanically different recount: POSIX find -name .git (file or directory)."""
    root = root.resolve()
    exclude = tuple(p.strip("/") for p in exclude_prefixes)
    proc = subprocess.run(
        ["find", str(root), "(", "-name", ".git", ")", "(", "-type", "f", "-o", "-type", "d", ")"],
        capture_output=True,
        text=True,
        check=False,
    )
    hits: list[dict] = []
    if proc.returncode not in (0, 1):
        return [
            {
                "path": "",
                "method": "find",
                "kind": "error",
                "form": "find-failed",
                "gitdir": None,
                "stderr": (proc.stderr or "")[:500],
                "exit_code": proc.returncode,
            }
        ]
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        path = Path(line)
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        if any(rel == p or rel.startswith(p + "/") for p in exclude):
            continue
        info = classify_git_entry(path)
        hits.append({"path": rel, "method": "find", **info})
    hits.sort(key=lambda r: r["path"])
    return hits


def paths_of(hits: list[dict]) -> list[str]:
    return sorted({h["path"] for h in hits if h.get("path")})
