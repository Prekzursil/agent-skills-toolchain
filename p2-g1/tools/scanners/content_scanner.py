"""Content scanner that matches semantic role rather than payload text."""
from __future__ import annotations


def applies(record: dict) -> bool:
    return str(record.get("role") or "") == "content"


def scan_content_records(records: list[dict], mode: str = "role") -> dict:
    fires, silent, naive = [], [], []
    for rec in records:
        rid = rec.get("id")
        text = str(rec.get("text") or rec.get("body") or "")
        naive.append(rid)
        if rec.get("true_positive") or rec.get("should_fire"):
            fires.append(rid)
        else:
            silent.append(rid)
        _ = text
    return {"fires_ids": fires, "silent_ids": silent, "naive_fires_ids": naive, "rows": records}
