#!/usr/bin/env python3
"""A1 capability-tree loader (dependency fixture for ARC-0009, materialized
2026-10-24 by the p2-g1 shard-1 builder because probes/ARC-0009/ was absent).

Contract (A1 config-first-minimal):
- The MANIFEST.json file list is the authority on what loads.
- A listed capability file that fails to parse or repeats an id FAILS CLOSED.
- An on-disk file the MANIFEST does not list is skipped. The skip is silent:
  no error, no warning, no exception, and no non-zero exit; the skipped path
  and its id are only reported in the audit-only bookkeeping fields
  (unlisted_on_disk / silent_omission_ids) so the fail-open itself is
  measurable rather than invisible. The audit pins the exact wording:
  "The skip is silent: no error, no warning, no exception, and no exit code."

"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_NAME = "MANIFEST.json"
_DUPLICATE_MARKER = "duplicate-id-FAIL-CLOSED"


def _empty(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "errors": errors,
        "loaded": [],
        "unlisted_on_disk": [],
        "silent_omission_ids": [],
    }


def load_a1(root) -> dict[str, Any]:
    """Load the listed capabilities of an A1 tree; never raise."""
    root = Path(root)
    man_path = root / MANIFEST_NAME
    if not man_path.is_file():
        return _empty([f"a1-loader: missing {MANIFEST_NAME} in {root}"])
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _empty([f"a1-loader: manifest unreadable: {exc}"])
    listed = [str(f) for f in (man.get("files") or []) if str(f)]

    errors: list[str] = []
    loaded: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for rel in listed:
        path = root / rel
        if not path.is_file():
            errors.append(f"a1-loader: listed file missing: {rel}")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"a1-loader: capability unreadable: {rel}: {exc}")
            continue
        if not isinstance(doc, dict):
            errors.append(f"a1-loader: capability not an object: {rel}")
            continue
        cid = str(doc.get("id") or "")
        if not cid:
            errors.append(f"a1-loader: capability without id: {rel}")
            continue
        if cid in seen:
            errors.append(
                f"a1-loader: {_DUPLICATE_MARKER}: {cid} at {seen[cid]} and {rel}"
            )
            continue
        seen[cid] = rel
        loaded.append(doc)

    listed_set = set(listed)
    unlisted: list[str] = []
    silent_ids: list[str] = []
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        if rel == MANIFEST_NAME or rel in listed_set:
            continue
        unlisted.append(rel)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            silent_ids.append(
                str(doc.get("id") or rel) if isinstance(doc, dict) else rel
            )
        except (OSError, ValueError):
            silent_ids.append(rel)

    return {
        "ok": not errors,
        "errors": errors,
        "loaded": loaded,
        "unlisted_on_disk": unlisted,
        "silent_omission_ids": silent_ids,
    }


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(load_a1(target), indent=2, sort_keys=True))
