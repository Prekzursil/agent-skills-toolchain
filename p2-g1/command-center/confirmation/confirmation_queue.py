"""Persistence for confirmation-queue entries (CNF-0139 trigger writes here)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_queue(path: Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"entries": []}
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return {"entries": []}
    doc.setdefault("entries", [])
    return doc


def save_queue(path: Path, doc: dict[str, Any]) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def enqueue(path: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    doc = load_queue(path)
    existing = list(doc.get("entries") or [])
    have = {str(e.get("unit_id")) for e in existing if isinstance(e, dict)}
    added = []
    for row in entries:
        uid = str(row.get("unit_id") or "")
        if uid and uid not in have:
            existing.append(row)
            have.add(uid)
            added.append(row)
    doc["entries"] = existing
    save_queue(path, doc)
    return {"added": added, "entries": existing}
