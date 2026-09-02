#!/usr/bin/env python3
"""Probe 2 instrument: git %cI vs live mtime, plus content-read of live-larger files."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from audit_common import REPO, iso_mtime
from lib_classify import decode, line_set


def git_committer_iso(repo_root: Path, rel: str) -> dict[str, Any]:
    """Signal 2: git log -1 --format=%cI. Records failure honestly."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%cI", "--", rel],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "exit_code": 127,
            "stdout": "",
            "stderr": f"{type(exc).__name__}:{exc}",
            "iso": None,
        }
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    return {
        "exit_code": proc.returncode,
        "stdout": out,
        "stderr": err,
        "iso": out or None,
    }


def content_read_live_larger(
    rel: str, repo_raw: bytes, live_raw: bytes
) -> dict[str, Any]:
    repo_text, live_text = decode(repo_raw), decode(live_raw)
    live_only = sorted(line_set(live_text) - line_set(repo_text))
    preview = live_raw[:800].decode("utf-8", errors="replace")
    return {
        "path": rel,
        "live_bytes": len(live_raw),
        "repo_bytes": len(repo_raw),
        "live_only_line_n": len(live_only),
        "live_only_lines": live_only,
        "live_head": preview,
        "read": True,
    }


def provenance_rows(
    repo_root: Path,
    live_root: Path,
    rels: list[str],
    *,
    git_root: Path | None = None,
) -> list[dict]:
    rows = []
    git_root = git_root or REPO
    for rel in rels:
        rp, lp = repo_root / rel, live_root / rel
        rec: dict[str, Any] = {
            "path": rel,
            "repo_exists": rp.is_file(),
            "live_exists": lp.is_file(),
            "live_mtime": iso_mtime(lp) if lp.is_file() else None,
            "repo_mtime": iso_mtime(rp) if rp.is_file() else None,
            "git": git_committer_iso(git_root, rel),
        }
        if rp.is_file() and lp.is_file():
            rb, lb = rp.read_bytes(), lp.read_bytes()
            rec["repo_bytes"] = len(rb)
            rec["live_bytes"] = len(lb)
            if len(lb) > len(rb):
                rec["live_larger_content"] = content_read_live_larger(rel, rb, lb)
        rows.append(rec)
    return rows
