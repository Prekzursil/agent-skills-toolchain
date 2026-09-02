"""A2 generated-SSOT analogue: completeness gate at generate time.

A generated single-source-of-truth architecture enumerates the registry
AND the on-disk capability files. An on-disk file with no registry entry
is FAIL-CLOSED (named), not silently omitted. That is the catch config-first
cannot perform: A1 has no generator (DESIGN precedence.no_generated_layer).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from a1_loader import disk_capability_files, listed_files


def check_a2_completeness(root: Path) -> dict[str, Any]:
    listed = listed_files(root)
    on_disk = disk_capability_files(root)
    listed_set = set(listed)
    disk_set = set(on_disk)
    orphans = sorted(disk_set - listed_set)
    missing = sorted(listed_set - disk_set)
    caught_ids: list[str] = []
    for rel in orphans:
        path = root / rel
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            caught_ids.append(str(body.get("id") or rel))
        except (OSError, json.JSONDecodeError):
            caught_ids.append(rel)
    ok = not orphans and not missing
    errors: list[str] = []
    if orphans:
        errors.append("orphan-on-disk-not-in-registry:" + ",".join(orphans))
    if missing:
        errors.append("registry-entry-missing-file:" + ",".join(missing))
    return {
        "ok": ok,
        "errors": errors,
        "orphans_on_disk": orphans,
        "missing_files": missing,
        "caught_ids": caught_ids,
        "architecture": "generated-SSOT",
        "gate": "completeness-at-generate-time",
    }
