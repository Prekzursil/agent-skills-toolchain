#!/usr/bin/env python3
"""Disposable mutating operator with one shared plan for dry-run and apply.

Dry-run returns the plan and writes nothing. Apply executes the same plan.
Lying dry-run omits a destructive delete that apply still performs.
Extra-write apply executes the plan then writes a file the plan never named.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

KEEP = "keep.txt"
VICTIM = "victim.txt"
STALE = "stale.txt"
NEW = "new.txt"
SNEAK = "sneak.txt"

KEEP_BODY = b"keep-v1\n"
VICTIM_BODY = b"victim-v1\n"
STALE_V1 = b"stale-v1\n"
STALE_V2 = b"stale-v2\n"
NEW_BODY = b"created-by-apply\n"
SNEAK_BODY = b"extra-write-not-in-plan\n"


def seed(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / KEEP).write_bytes(KEEP_BODY)
    (root / VICTIM).write_bytes(VICTIM_BODY)
    (root / STALE).write_bytes(STALE_V1)


def plan() -> list[dict[str, Any]]:
    """Ordered filesystem mutations. Shared by dry-run and apply."""
    return [
        {"op": "create", "path": NEW, "bytes": len(NEW_BODY)},
        {"op": "overwrite", "path": STALE, "bytes": len(STALE_V2)},
        {"op": "delete", "path": VICTIM, "bytes": len(VICTIM_BODY)},
    ]


def lying_plan() -> list[dict[str, Any]]:
    """Known-broken dry-run: omit the destructive delete."""
    return [step for step in plan() if not (step["op"] == "delete" and step["path"] == VICTIM)]


def dry_run() -> list[dict[str, Any]]:
    return [dict(step) for step in plan()]


def apply(root: Path) -> None:
    (root / NEW).write_bytes(NEW_BODY)
    (root / STALE).write_bytes(STALE_V2)
    victim = root / VICTIM
    if victim.exists():
        victim.unlink()


def apply_lying(root: Path) -> None:
    """Real run still deletes victim.txt even though lying_plan omitted it."""
    apply(root)


def apply_extra_write(root: Path) -> None:
    apply(root)
    (root / SNEAK).write_bytes(SNEAK_BODY)
