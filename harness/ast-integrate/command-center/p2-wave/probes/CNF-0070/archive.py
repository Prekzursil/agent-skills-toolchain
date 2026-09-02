#!/usr/bin/env python3
"""Local archival snapshot service and quote/untrusted scanners.

Archived bodies are untrusted data: they are read as text, scanned, and
diffed. They are never compiled, eval'd, or passed to a shell.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
EXEC_MARKER = HERE / "CNF-0070-EXECUTED.marker"

UNTRUSTED_PATTERNS = [
    re.compile(r"ignore previous instructions", re.I),
    re.compile(r"CNF-0070-UNTRUSTED-INSTRUCTION"),
    re.compile(r"python3?\s+-c\s+"),
    re.compile(r"os\.system\s*\("),
    re.compile(r"subprocess\."),
    re.compile(r"<script[\s>]", re.I),
    re.compile(r"rm\s+-rf\s+"),
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_date(value: str) -> date:
    raw = (value or "").strip()
    if "T" in raw:
        return parse_datetime(raw).date()
    return date.fromisoformat(raw[:10])


def parse_datetime(value: str) -> datetime:
    raw = (value or "").strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def capture_on_or_before(capture_timestamp: str, citation_date: str) -> bool:
    """A snapshot establishes citation-time truth iff its capture date <= citation date."""
    return parse_datetime(capture_timestamp).date() <= parse_date(citation_date)


def locate_quote(body: str, quote: str) -> dict:
    if not quote:
        return {"found": False, "offset": None, "located_quote": None}
    idx = body.find(quote)
    if idx < 0:
        return {"found": False, "offset": None, "located_quote": None}
    return {"found": True, "offset": idx, "located_quote": quote}


def scan_untrusted(body: str) -> list[dict]:
    hits: list[dict] = []
    for pat in UNTRUSTED_PATTERNS:
        for m in pat.finditer(body):
            start = max(0, m.start() - 40)
            end = min(len(body), m.end() + 80)
            hits.append(
                {
                    "pattern": pat.pattern,
                    "offset": m.start(),
                    "span": body[start:end].replace("\n", " ")[:160],
                }
            )
    return hits


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_archive_index() -> dict:
    return load_json(FIX / "archive-index.json")


def load_live_index() -> dict:
    return load_json(FIX / "live-index.json")


def read_fixture(rel: str) -> str:
    path = FIX / rel
    return path.read_text(encoding="utf-8")


def snapshot_url(page_url: str, capture_timestamp: str) -> str:
    return f"fixture://archive/{page_url}?ts={capture_timestamp}"


def live_page(url: str) -> dict:
    pages = load_live_index().get("pages") or {}
    rel = pages.get(url)
    if not rel:
        return {
            "reachable": False,
            "http_status": 404,
            "body": "",
            "body_path": None,
            "sha256": None,
        }
    body = read_fixture(rel)
    return {
        "reachable": True,
        "http_status": 200,
        "body": body,
        "body_path": f"command-center/p2-wave/probes/CNF-0070/fixtures/{rel}",
        "sha256": sha256_text(body),
    }


def snapshots_for(url: str) -> list[dict]:
    index = load_archive_index().get("snapshots") or {}
    rows = []
    for item in index.get(url) or []:
        rel = str(item["body"])
        body = read_fixture(rel)
        rows.append(
            {
                "capture_timestamp": item["capture_timestamp"],
                "body": body,
                "body_path": f"command-center/p2-wave/probes/CNF-0070/fixtures/{rel}",
                "sha256": sha256_text(body),
                "snapshot_url": snapshot_url(url, item["capture_timestamp"]),
            }
        )
    return rows


def never_execute_archived(body: str) -> None:
    """Explicit non-execution: record only. Do not eval, exec, or subprocess body."""
    _ = body
    if EXEC_MARKER.is_file():
        # A prior buggy run is not evidence this run executed anything; probes
        # delete the marker before auditing.
        pass
    return None
