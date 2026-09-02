#!/usr/bin/env python3
"""Uninstall contract: remove claimed files only; preserve owner/user/MCP state.

Two independent readings of preservation:
  signal 1 — Python sha256 of each preserved file vs a pre-uninstall snapshot
  signal 2 — bash `cmp -s` plus `stat -c %s` (different shell, different field)

Disagreeing readings are BLOCKED, not a picked winner.
A wipe that would delete a hand-authored file must be caught.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from estate import CLAIMED_LIVE_RELS, OWNER_NOTE, PRESERVE_RELS, lf_bytes


def sha256_file(path: Path) -> str:
    return hashlib.sha256(lf_bytes(path.read_bytes())).hexdigest()


def snapshot_preserve(estate: Path, snap: Path) -> None:
    snap.mkdir(parents=True, exist_ok=True)
    for rel in PRESERVE_RELS:
        src = estate / rel
        dest = snap / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def legal_uninstall(
    estate: Path, claimed: tuple[str, ...] | list[str] = CLAIMED_LIVE_RELS
) -> list[str]:
    removed: list[str] = []
    for rel in claimed:
        path = estate / rel
        if path.is_file():
            path.unlink()
            removed.append(rel)
    return removed


def wipe_uninstall(estate: Path) -> list[str]:
    """Negative control: deletes claimed files AND the hand-authored overlay."""
    removed = legal_uninstall(estate)
    extra = estate / OWNER_NOTE
    if extra.is_file():
        extra.unlink()
        removed.append(OWNER_NOTE)
    return removed


def signal1_sha256(estate: Path, snap: Path) -> dict[str, Any]:
    intact = 0
    failed: list[str] = []
    rows: list[dict[str, Any]] = []
    for rel in PRESERVE_RELS:
        live = estate / rel
        base = snap / rel
        if not live.is_file() or not base.is_file():
            failed.append(rel)
            rows.append({"path": rel, "match": False, "reason": "missing"})
            continue
        live_sha = sha256_file(live)
        base_sha = sha256_file(base)
        match = live_sha == base_sha
        if match:
            intact += 1
        else:
            failed.append(rel)
        rows.append(
            {
                "path": rel,
                "match": match,
                "live_sha256": live_sha,
                "snap_sha256": base_sha,
            }
        )
    return {
        "id": "signal-1-python-sha256",
        "intact": intact,
        "failed": failed,
        "rows": rows,
    }


def signal2_bash_cmp(estate: Path, snap: Path) -> dict[str, Any]:
    """Different shell (bash) and different field (cmp exit + byte size)."""
    intact = 0
    failed: list[str] = []
    rows: list[dict[str, Any]] = []
    base_env = os.environ.copy()
    for rel in PRESERVE_RELS:
        live = estate / rel
        base = snap / rel
        if not live.is_file() or not base.is_file():
            failed.append(rel)
            rows.append({"path": rel, "cmp_exit": 2, "size_match": False})
            continue
        env = {**base_env, "LIVE": str(live), "SNAP": str(base)}
        cmp_p = subprocess.run(
            ["bash", "-c", 'cmp -s -- "$LIVE" "$SNAP"; printf %s "$?"'],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        try:
            cmp_exit = int((cmp_p.stdout or "2").strip() or "2")
        except ValueError:
            cmp_exit = 2
        size_p = subprocess.run(
            [
                "bash",
                "-c",
                'printf "%s %s" "$(stat -c %s -- "$LIVE")" "$(stat -c %s -- "$SNAP")"',
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        parts = (size_p.stdout or "").strip().split()
        try:
            live_size, snap_size = int(parts[0]), int(parts[1])
        except (IndexError, ValueError):
            live_size, snap_size = -1, -2
        size_match = live_size == snap_size and live_size >= 0
        ok = cmp_exit == 0 and size_match
        if ok:
            intact += 1
        else:
            failed.append(rel)
        rows.append(
            {
                "path": rel,
                "cmp_exit": cmp_exit,
                "live_bytes": live_size,
                "snap_bytes": snap_size,
                "size_match": size_match,
            }
        )
    return {
        "id": "signal-2-bash-cmp-and-stat-size",
        "intact": intact,
        "failed": failed,
        "rows": rows,
    }


def claimed_removed(
    estate: Path, claimed: tuple[str, ...] | list[str] = CLAIMED_LIVE_RELS
) -> bool:
    return all(not (estate / rel).is_file() for rel in claimed)


def preservation_report(estate: Path, snap: Path) -> dict[str, Any]:
    s1 = signal1_sha256(estate, snap)
    s2 = signal2_bash_cmp(estate, snap)
    disagree = s1["intact"] != s2["intact"]
    owner_ok = (estate / PRESERVE_RELS[0]).is_file() and PRESERVE_RELS[0] not in s1["failed"]
    user_ok = (estate / PRESERVE_RELS[1]).is_file() and PRESERVE_RELS[1] not in s1["failed"]
    mcp_ok = (estate / PRESERVE_RELS[2]).is_file() and PRESERVE_RELS[2] not in s1["failed"]
    removed = claimed_removed(estate)
    passed = (
        not disagree
        and s1["intact"] == len(PRESERVE_RELS)
        and s2["intact"] == len(PRESERVE_RELS)
        and owner_ok
        and user_ok
        and mcp_ok
        and removed
        and not s1["failed"]
        and not s2["failed"]
    )
    return {
        "pass": passed,
        "files_checked": len(PRESERVE_RELS),
        "files_failed": list(s1["failed"]),
        "owner_authored_intact": owner_ok,
        "user_data_intact": user_ok,
        "mcp_state_intact": mcp_ok,
        "claimed_removed": removed,
        "signal1_sha256_intact": s1["intact"],
        "signal2_cmp_intact": s2["intact"],
        "signal_disagreement": disagree,
        "signal1": s1,
        "signal2": s2,
    }


def negative_control(estate: Path, snap: Path) -> dict[str, Any]:
    """A wipe that would remove the hand-authored overlay must be caught."""
    wipe_uninstall(estate)
    report = preservation_report(estate, snap)
    caught = (not (estate / OWNER_NOTE).is_file()) or (not report["owner_authored_intact"])
    check_failed = not report["pass"]
    return {
        "id": "wipe-would-remove-owner-overlay",
        "would_have_removed": OWNER_NOTE,
        "caught": bool(caught and check_failed),
        "pass": bool(caught and check_failed),
        "reason": (
            "wipe_uninstall deleted the hand-authored overlay; preservation "
            "check failed closed instead of reporting green"
        ),
        "preservation_pass_after_wipe": report["pass"],
        "owner_present_after_wipe": (estate / OWNER_NOTE).is_file(),
    }
