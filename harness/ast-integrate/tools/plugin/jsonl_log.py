"""Bounded JSONL logger with mandatory secret redaction (IMP-0056)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECRET_RE = re.compile(
    r"(ghp_[A-Za-z0-9_]+|sk-[A-Za-z0-9]+|xoxb-[A-Za-z0-9-]+|AKIA[0-9A-Z]{16})"
)
REDACTED = "[REDACTED]"


def _redact_text(text: str) -> str:
    return SECRET_RE.sub(REDACTED, text)


def _redact(obj: Any) -> Any:
    if isinstance(obj, str):
        return _redact_text(obj)
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if str(key).lower() in {"token", "secret", "password", "authorization"}:
                out[key] = REDACTED
            else:
                out[key] = _redact(value)
        return out
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


class JsonlLogger:
    def __init__(
        self,
        path: str | Path,
        unit_id: str,
        redact: bool = True,
        max_bytes: int = 1_048_576,
        max_files: int = 3,
        **kwargs,
    ) -> None:
        self.path = Path(path)
        self.unit_id = unit_id
        self.redact = redact
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, error_code: str, **fields: Any) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "unit_id": self.unit_id,
            "error_code": error_code,
            "fields": dict(fields),
        }
        if self.redact:
            rec = _redact(rec)
            rec["unit_id"] = self.unit_id
            rec["error_code"] = error_code
        line = json.dumps(rec, ensure_ascii=True, separators=(",", ":")) + "\n"
        existing = self.path.read_bytes() if self.path.is_file() else b""
        blob = existing + line.encode("utf-8")
        if len(blob) > self.max_bytes:
            blob = blob[-self.max_bytes :]
        self.path.write_bytes(blob)
        return rec


__all__ = ["JsonlLogger", "REDACTED"]
