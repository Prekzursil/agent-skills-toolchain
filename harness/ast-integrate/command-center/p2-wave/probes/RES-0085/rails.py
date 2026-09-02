#!/usr/bin/env python3
"""Load captured evidence rails (permalink, timestamp, HTTP status, sha256)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "fixtures" / "captures"
INDEX = CAP / "index.json"


def load_index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def rail(capture_id: str) -> dict:
    idx = load_index()
    for rec in idx.get("captures") or []:
        if rec.get("id") == capture_id:
            meta_path = CAP / f"{capture_id}.meta.json"
            body_path = CAP / f"{capture_id}.body"
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else rec
            present = body_path.is_file()
            return {
                "capture_id": capture_id,
                "kind": rec.get("kind") or rec.get("rail"),
                "rail_class": rec.get("rail"),
                "permalink": rec.get("permalink"),
                "resolved_url": rec.get("resolved_url"),
                "doi": rec.get("doi"),
                "fetched_at": rec.get("fetched_at"),
                "http_status": rec.get("http_status"),
                "bytes": rec.get("bytes"),
                "sha256": rec.get("sha256"),
                "body_present": present,
                "ok": bool(rec.get("ok")),
            } | ({"meta_ok": True} if meta else {})
    raise KeyError(capture_id)


def require_two_rails(structured_id: str, prose_id: str) -> list[dict]:
    a, b = rail(structured_id), rail(prose_id)
    if a.get("rail_class") == b.get("rail_class"):
        raise ValueError(f"rails not independent classes: {a.get('rail_class')}")
    for r in (a, b):
        if not r.get("ok") or r.get("http_status") != 200 or not r.get("sha256"):
            raise ValueError(f"dead rail {r.get('capture_id')}")
        if r.get("rail_class") not in {"structured-api", "prose"}:
            raise ValueError(f"bad rail class {r}")
    if a["rail_class"] != "structured-api" or b["rail_class"] != "prose":
        raise ValueError("expected structured-api then prose")
    return [a, b]
