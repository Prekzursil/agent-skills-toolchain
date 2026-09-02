"""Declared downstream consumer for CNF-0192 (completion-predicate condition 12).

Existence is not readability. This module opens the file, parses it, and
extracts required fields. A path that stats successfully but lacks
``consumer_token == READABLE`` is UNREADABLE-BY-CONSUMER.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONSUMER_ID = "cnf-0192.json-object-required-field-reader"
REQUIRED_KEYS = ("id", "kind", "consumer_token")
READABLE_TOKEN = "READABLE"


def consume(path: Path, required_keys: tuple[str, ...] = REQUIRED_KEYS) -> dict[str, Any]:
    """Open, parse, and extract. Never a stat-only check."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {
            "ok": False,
            "class": "unreadable-by-consumer",
            "consumer_id": CONSUMER_ID,
            "reason": f"open-failed:{type(exc).__name__}",
            "bytes_read": 0,
            "stat_only": False,
            "opened": False,
        }
    if len(raw) == 0:
        return {
            "ok": False,
            "class": "empty",
            "consumer_id": CONSUMER_ID,
            "reason": "zero-byte-after-open",
            "bytes_read": 0,
            "stat_only": False,
            "opened": True,
        }
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "class": "unreadable-by-consumer",
            "consumer_id": CONSUMER_ID,
            "reason": f"parse-failed:{type(exc).__name__}",
            "bytes_read": len(raw),
            "stat_only": False,
            "opened": True,
        }
    if not isinstance(doc, dict):
        return {
            "ok": False,
            "class": "unreadable-by-consumer",
            "consumer_id": CONSUMER_ID,
            "reason": "not-a-json-object",
            "bytes_read": len(raw),
            "stat_only": False,
            "opened": True,
            "parsed_type": type(doc).__name__,
        }
    missing = [k for k in required_keys if k not in doc]
    if missing:
        return {
            "ok": False,
            "class": "unreadable-by-consumer",
            "consumer_id": CONSUMER_ID,
            "reason": f"missing-required-keys:{missing}",
            "bytes_read": len(raw),
            "stat_only": False,
            "opened": True,
            "parsed_keys": list(doc.keys()),
            "first_key": next(iter(doc)),
        }
    if doc.get("consumer_token") != READABLE_TOKEN:
        return {
            "ok": False,
            "class": "unreadable-by-consumer",
            "consumer_id": CONSUMER_ID,
            "reason": "consumer_token-not-READABLE",
            "bytes_read": len(raw),
            "stat_only": False,
            "opened": True,
            "parsed_keys": list(doc.keys()),
            "first_key": next(iter(doc)),
        }
    keys = list(doc.keys())
    return {
        "ok": True,
        "class": "verified",
        "consumer_id": CONSUMER_ID,
        "bytes_read": len(raw),
        "stat_only": False,
        "opened": True,
        "parsed_keys": keys,
        "first_key": keys[0],
        "extracted_id": doc.get("id"),
        "extracted_kind": doc.get("kind"),
        "record_count": 1,
    }


CHARTER_CONSUMER_ID = "cnf-0192.charter-open-decode"


def consume_open_decode(path: Path) -> dict[str, Any]:
    """Declared consumer for live charter files (md/json/jsonl).

    Opens and reads. A successful stat is not a pass. UTF-8 decode is required;
    JSON parse is recorded when the bytes are a JSON object, but is not required
    for markdown or jsonl.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {
            "ok": False,
            "class": "unreadable-by-consumer",
            "consumer_id": CHARTER_CONSUMER_ID,
            "reason": f"open-failed:{type(exc).__name__}",
            "bytes_read": 0,
            "stat_only": False,
            "opened": False,
        }
    if len(raw) == 0:
        return {
            "ok": False,
            "class": "empty",
            "consumer_id": CHARTER_CONSUMER_ID,
            "reason": "zero-byte-after-open",
            "bytes_read": 0,
            "stat_only": False,
            "opened": True,
        }
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "ok": False,
            "class": "unreadable-by-consumer",
            "consumer_id": CHARTER_CONSUMER_ID,
            "reason": "utf8-decode-failed",
            "bytes_read": len(raw),
            "stat_only": False,
            "opened": True,
        }
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    first_key: str | None = first_line[:120] if first_line else None
    parsed_keys = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed:
            parsed_keys = list(parsed.keys())[:24]
            first_key = str(parsed_keys[0])
    except json.JSONDecodeError:
        pass
    return {
        "ok": True,
        "class": "verified",
        "consumer_id": CHARTER_CONSUMER_ID,
        "bytes_read": len(raw),
        "stat_only": False,
        "opened": True,
        "first_key": first_key,
        "parsed_keys": parsed_keys,
        "record_count": 1,
    }
