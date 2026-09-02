#!/usr/bin/env python3
"""Locate the two catalog corpus trees. Absence is recorded, never invented.

Two independent signals per candidate: pathlib.Path.is_dir and `test -d`.
Fixture control trees are not candidates for the live corpus.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

TREE_A = "platform-redesign-2026-07-19"
TREE_B = "harness-restore-20260806"

ENV_A = "RES0127_PLATFORM_ROOT"
ENV_B = "RES0127_HARNESS_ROOT"


def _candidates(name: str, env_key: str) -> list[Path]:
    out: list[Path] = []
    env = os.environ.get(env_key, "").strip()
    if env:
        out.append(Path(env))
    home = Path.home()
    out.extend(
        [
            home / ".claude" / name,
            Path("/root/.claude") / name,
            Path("/mnt/c/Users/Prekzursil/.claude") / name,
            Path("/c/Users/Prekzursil/.claude") / name,
            Path("/Users/Prekzursil/.claude") / name,
            REPO / name,
            REPO.parent / name,
            Path("/opt/p2") / name,
            Path("/tmp") / name,
        ]
    )
    # de-dupe while preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _test_d(path: Path) -> bool:
    try:
        proc = subprocess.run(
            ["test", "-d", str(path)],
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def probe_path(path: Path) -> dict[str, Any]:
    try:
        pathlib_dir = path.is_dir()
    except OSError:
        pathlib_dir = False
    test_d = _test_d(path)
    listing_n = None
    if pathlib_dir:
        try:
            listing_n = sum(1 for _ in path.iterdir())
        except OSError:
            listing_n = None
    return {
        "path": str(path).replace("\\", "/"),
        "pathlib_is_dir": pathlib_dir,
        "test_d": test_d,
        "signals_agree": pathlib_dir == test_d,
        "present": bool(pathlib_dir and test_d),
        "listing_n": listing_n,
    }


def locate_one(name: str, env_key: str) -> dict[str, Any]:
    searched = [probe_path(p) for p in _candidates(name, env_key)]
    hits = [row for row in searched if row["present"]]
    chosen = hits[0] if hits else None
    return {
        "name": name,
        "present": chosen is not None,
        "root": chosen["path"] if chosen else None,
        "searched": searched,
        "n_hits": len(hits),
        "disagreeing_signals": [
            row["path"] for row in searched if not row["signals_agree"]
        ],
    }


def locate_trees() -> dict[str, Any]:
    a = locate_one(TREE_A, ENV_A)
    b = locate_one(TREE_B, ENV_B)
    return {
        "tree_a": TREE_A,
        "tree_b": TREE_B,
        "platform_redesign": a,
        "harness_restore": b,
        "both_present": bool(a["present"] and b["present"]),
        "either_present": bool(a["present"] or b["present"]),
    }
