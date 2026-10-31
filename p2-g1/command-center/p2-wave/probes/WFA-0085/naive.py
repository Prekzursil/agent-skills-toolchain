"""Negative control: append-only ingest that duplicates colliding identities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from identity import canonical_id, content_hash
from sweep import source_files


def append_all(corpus: Path, migration_map: dict[str, str]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for src_path in source_files(corpus):
        src = json.loads(src_path.read_text(encoding="utf-8"))
        raw = str(src.get("id") or "")
        records.append(
            {
                "body": src.get("body"),
                "content_hash": content_hash(src),
                "family": src.get("family"),
                "mechanism": src.get("mechanism"),
                "raw_id": raw,
                "source_file": src_path.name,
                "source_uri": src.get("source_uri"),
                "stable_id": canonical_id(raw, migration_map),
                "title": src.get("title"),
            }
        )
    ids = [r["stable_id"] for r in records]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    return {
        "n_records": len(records),
        "n_unique_ids": len(set(ids)),
        "duplicate_ids": dupes,
        "duplicates": bool(dupes),
        "ids": ids,
    }
