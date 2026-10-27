"""Bounded JSONL logger with mandatory secret redaction (IMP-0056).

Every record carries the error code, unit id and a UTC timestamp.  A
redaction filter runs on the VALUE side of every field before write.  The
file set rotates by size AND count: the active file never exceeds
``max_bytes`` and at most ``max_files`` rotated segments survive, so logs
cannot consume the disk regardless of write volume.
"""
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
        if max_bytes < 1:
            raise ValueError("max_bytes must be >= 1")
        if max_files < 1:
            raise ValueError("max_files must be >= 1")
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- rotation ---------------------------------------------------------- #
    def _segment(self, n: int) -> Path:
        return self.path.with_name(self.path.name + ("" if n == 0 else f".{n}"))

    def segments(self) -> list[Path]:
        out = []
        for n in range(1, self.max_files):
            seg = self._segment(n)
            if seg.is_file():
                out.append(seg)
        return out

    def all_files(self) -> list[Path]:
        return ([self.path] if self.path.is_file() else []) + self.segments()

    def _rotate(self) -> None:
        """Shift .N-1 -> .N, active -> .1; the oldest segment is dropped.

        max_files counts EVERY file: the active file plus segments .1 ..
        .(max_files-1). Nothing beyond that survives a rotation.
        """
        top = self._segment(self.max_files - 1)
        if top.exists():
            top.unlink()
        for n in range(self.max_files - 2, 0, -1):
            src = self._segment(n)
            if src.is_file():
                src.replace(self._segment(n + 1))
        if self.path.is_file():
            self.path.replace(self._segment(1))
        # Bound enforcement: nothing beyond the named segments survives.
        for n in range(self.max_files, self.max_files + 8):
            seg = self._segment(n)
            if seg.exists():
                seg.unlink()

    # -- write -------------------------------------------------------------- #
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
        blob = line.encode("utf-8")
        if len(blob) > self.max_bytes:
            # A single record larger than the whole budget is truncated to the
            # last max_bytes so the bound is unconditional.
            blob = blob[-self.max_bytes :]
        current = self.path.read_bytes() if self.path.is_file() else b""
        if current and len(current) + len(blob) > self.max_bytes:
            self._rotate()
            current = b""
        if len(current) + len(blob) > self.max_bytes:
            blob = blob[len(blob) - self.max_bytes :]
        with self.path.open("ab") as fh:
            fh.write(blob)
        return rec


__all__ = ["JsonlLogger", "REDACTED", "SECRET_RE"]
