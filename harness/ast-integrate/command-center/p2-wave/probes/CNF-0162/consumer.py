"""Declared downstream consumer for completion-predicate condition 12.

Existence and JSON syntax are not readability. This consumer opens the
file and extracts the fields a command-center receipt gate actually uses:
unit_id, state, sentinel. A document that parses but lacks those fields
fails condition 12.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONSUMER_ID = "cnf-0162.receipt-field-consumer"
REQUIRED_FIELDS = ("unit_id", "state", "sentinel")


class ConsumerError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _unit_id(doc: dict[str, Any]) -> str:
    for key in ("unit_id", "id"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _state(doc: dict[str, Any]) -> str:
    for key in ("state", "status"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _sentinel(doc: dict[str, Any]) -> str:
    for key in ("sentinel", "completion_sentinel"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def consume(path: Path) -> dict[str, Any]:
    """Open `path` and return the fields this consumer requires.

    Raises ConsumerError on any failure. Callers must not treat a raised
    error as a silent skip.
    """
    if not path.is_file():
        raise ConsumerError("missing", f"not a file: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConsumerError("unreadable", f"{type(exc).__name__}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConsumerError("unparseable", f"{type(exc).__name__}") from exc
    if not isinstance(doc, dict):
        raise ConsumerError("not-object", f"root is {type(doc).__name__}")
    extracted = {
        "unit_id": _unit_id(doc),
        "state": _state(doc),
        "sentinel": _sentinel(doc),
    }
    missing = [k for k in REQUIRED_FIELDS if not extracted[k]]
    if missing:
        raise ConsumerError("missing-field", "missing " + ",".join(missing))
    return {
        "consumer_id": CONSUMER_ID,
        "path": str(path),
        "bytes": len(raw),
        "extracted": extracted,
    }
