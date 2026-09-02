#!/usr/bin/env python3
"""Freeze gate: a frozen-path hash change is REJECT without a versioned migration.

A versioned migration must carry from_version, to_version (strict bump),
paths, transform, reversibility statement, and an executed dry-run result.
A record whose transform was never executed is NOT-CHECKED and does not admit
the change. Edits to paths outside the frozen set are ignored (scope).
"""
from __future__ import annotations

from typing import Any

from hashutil import digest_bytes

REQUIRED_MIGRATION_FIELDS = (
    "from_version",
    "to_version",
    "paths",
    "transform",
    "reversibility",
    "dry_run_result",
)


def overlay_bytes(
    repo,
    rel: str,
    overlay: dict[str, bytes] | None,
) -> bytes:
    if overlay and rel in overlay:
        return overlay[rel]
    return (repo / rel).read_bytes()


def migration_covers(rec: dict[str, Any], rel: str, frozen_version: int) -> tuple[bool, str]:
    missing = [k for k in REQUIRED_MIGRATION_FIELDS if k not in rec]
    if missing:
        return False, f"missing-fields:{','.join(missing)}"
    paths = rec.get("paths") or []
    if rel not in paths:
        return False, "path-not-covered"
    try:
        frm = int(rec["from_version"])
        to = int(rec["to_version"])
    except (TypeError, ValueError):
        return False, "versions-not-int"
    if frm != int(frozen_version):
        return False, "from-version-mismatch"
    if to <= frm:
        return False, "no-version-bump"
    transform = rec.get("transform")
    if not isinstance(transform, dict) or not str(transform.get("description") or "").strip():
        return False, "transform-empty"
    rev = rec.get("reversibility")
    if not isinstance(rev, dict) or "reversible" not in rev:
        return False, "reversibility-missing"
    if not str(rev.get("statement") or "").strip():
        return False, "reversibility-statement-empty"
    dry = rec.get("dry_run_result")
    if not isinstance(dry, dict):
        return False, "dry-run-not-object"
    if dry.get("ran") is not True:
        return False, "NOT-CHECKED-dry-run-not-executed"
    if dry.get("ok") is not True:
        return False, "dry-run-failed"
    return True, "ok"


def evaluate(
    repo,
    frozen: list[dict[str, Any]],
    *,
    overlay: dict[str, bytes] | None = None,
    migrations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    migrations = list(migrations or [])
    overlay = overlay or {}
    rejections: list[dict[str, str]] = []
    changed: list[dict[str, Any]] = []
    ignored: list[str] = []
    frozen_paths = {row["path"] for row in frozen}

    for rel in sorted(overlay):
        if rel not in frozen_paths:
            ignored.append(rel)

    by_path = {row["path"]: row for row in frozen}
    for rel, row in sorted(by_path.items()):
        current = overlay_bytes(repo, rel, overlay)
        sha, _ = digest_bytes(current)
        if sha == row["sha256"]:
            continue
        recs = [m for m in migrations if rel in (m.get("paths") or [])]
        if not recs:
            rejections.append({"path": rel, "reason": "unmigrated-change"})
            changed.append({"path": rel, "from_sha256": row["sha256"], "to_sha256": sha})
            continue
        ok = False
        last_why = "no-covering-migration"
        for rec in recs:
            covered, last_why = migration_covers(rec, rel, int(row.get("content_version") or 1))
            if covered:
                ok = True
                break
        changed.append(
            {
                "path": rel,
                "from_sha256": row["sha256"],
                "to_sha256": sha,
                "admitted": ok,
                "reason": last_why,
            }
        )
        if not ok:
            rejections.append({"path": rel, "reason": last_why})

    ok = not rejections
    return {
        "ok": ok,
        "verdict": "ACCEPT" if ok else "REJECT",
        "reason": "clean-or-migrated" if ok else rejections[0]["reason"],
        "changed_frozen": changed,
        "rejections": rejections,
        "nonfrozen_changes_ignored": ignored,
        "frozen_checked": len(frozen),
    }
