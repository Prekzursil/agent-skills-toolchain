"""Load the 96-entry library and count unique ids."""
from __future__ import annotations

from typing import Any

from blueprint_library.inventory import DELEGATED_IDS, PHASE7_RECORDS


def load_library() -> list[dict[str, Any]]:
    rows = [{"id": i, "kind": "phase7"} for i in PHASE7_RECORDS]
    rows.extend({"id": i, "kind": "delegated"} for i in DELEGATED_IDS)
    return rows


def library_counts(entries: list[dict[str, Any]] | None = None) -> dict[str, int]:
    entries = entries if entries is not None else load_library()
    phase7 = sum(1 for e in entries if e.get("kind") == "phase7")
    delegated = sum(1 for e in entries if e.get("kind") == "delegated")
    ids = [e["id"] for e in entries]
    return {
        "phase7": phase7,
        "delegated": delegated,
        "total": len(entries),
        "unique_ids": len(set(ids)),
    }
