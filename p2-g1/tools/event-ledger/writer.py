"""Append-only JSONL ledger writer: durable write precedes RAM apply."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_record(path: Path, rec: dict[str, Any]) -> dict[str, Any]:
    """Append one record as a JSON line. Creates parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=True) + "\n")
    return rec


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read every well-formed JSON object line from the ledger file."""
    path = Path(path)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def next_seq(path: Path) -> int:
    """Next monotone sequence number derived from the durable file."""
    return max((int(r.get("seq") or 0) for r in read_records(path)), default=0) + 1
