"""Walk JSON/text and strip enumerated identity tokens."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from identities import redact_text


def redact_value(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, list):
        return [redact_value(item) for item in obj]
    if isinstance(obj, dict):
        return {redact_value(k) if isinstance(k, str) else k: redact_value(v) for k, v in obj.items()}
    return obj


def deidentify_bytes(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return (redact_text(text) + ("" if text.endswith("\n") else "\n")).encode("utf-8")
    redacted = redact_value(obj)
    dumped = json.dumps(redacted, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    return dumped.encode("utf-8")


def deidentify_file(src: Path, dst: Path) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    out = deidentify_bytes(src.read_bytes())
    dst.write_bytes(out)
    return len(out)
