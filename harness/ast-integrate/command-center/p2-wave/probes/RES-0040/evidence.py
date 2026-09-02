#!/usr/bin/env python3
"""Load captured evidence rails (permalink, timestamp, HTTP status, sha256)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"


def load_index() -> dict[str, Any]:
    path = CAP / "INDEX.json"
    return json.loads(path.read_text(encoding="utf-8"))


def rails_for(client_id: str) -> list[dict[str, Any]]:
    idx = load_index()
    rows = []
    for src in idx.get("sources") or []:
        if src.get("client_id") != client_id:
            continue
        if int(src.get("http_status") or 0) != 200:
            continue
        rows.append(
            {
                "id": src["id"],
                "rail": src["rail"],
                "permalink": src.get("final_url") or src.get("url"),
                "url": src.get("url"),
                "fetched_at": src.get("fetched_at"),
                "http_status": src.get("http_status"),
                "sha256": src.get("sha256"),
                "bytes": src.get("bytes"),
            }
        )
    return rows


def require_two_rails(client_id: str) -> list[dict[str, Any]]:
    rows = rails_for(client_id)
    kinds = {r["rail"] for r in rows}
    if len(rows) < 2:
        raise RuntimeError(f"{client_id}: need two evidence rails, got {len(rows)}")
    # Prefer mixed R1+R2 when both exist; otherwise two independent URLs.
    if "R1-structured" in kinds and "R2-prose" in kinds:
        mixed = []
        seen = set()
        for want in ("R1-structured", "R2-prose"):
            for r in rows:
                if r["rail"] == want and r["id"] not in seen:
                    mixed.append(r)
                    seen.add(r["id"])
                    break
        return mixed
    return rows[:2]


def all_rails() -> list[dict[str, Any]]:
    idx = load_index()
    out = []
    for src in idx.get("sources") or []:
        if int(src.get("http_status") or 0) != 200:
            continue
        out.append(
            {
                "id": src["id"],
                "client_id": src["client_id"],
                "rail": src["rail"],
                "permalink": src.get("final_url") or src.get("url"),
                "fetched_at": src.get("fetched_at"),
                "http_status": src.get("http_status"),
                "sha256": src.get("sha256"),
                "bytes": src.get("bytes"),
            }
        )
    return out
