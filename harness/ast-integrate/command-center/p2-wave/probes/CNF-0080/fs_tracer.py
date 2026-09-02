#!/usr/bin/env python3
"""Filesystem tracer: census of real bytes, not log claims.

A before/after hash of every file under a disposable root is the verdict.
A write that never hits disk is not a write, even if a log said it happened.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def census(root: Path) -> dict[str, dict[str, Any]]:
    root = root.resolve()
    out: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        out[rel] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    return out


def diff_census(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for rel in sorted(set(before) | set(after)):
        if rel not in before:
            actions.append(
                {
                    "op": "create",
                    "path": rel,
                    "bytes": after[rel]["bytes"],
                    "sha256": after[rel]["sha256"],
                }
            )
        elif rel not in after:
            actions.append(
                {
                    "op": "delete",
                    "path": rel,
                    "bytes": before[rel]["bytes"],
                    "sha256": before[rel]["sha256"],
                }
            )
        elif before[rel]["sha256"] != after[rel]["sha256"]:
            actions.append(
                {
                    "op": "overwrite",
                    "path": rel,
                    "bytes": after[rel]["bytes"],
                    "sha256": after[rel]["sha256"],
                }
            )
    return actions


def keyset(actions: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(str(a.get("op")), str(a.get("path"))) for a in actions]
