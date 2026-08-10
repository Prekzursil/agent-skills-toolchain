"""Structured logging with MANDATORY deny-by-default redaction and bounded rotation.

Two non-negotiables:

* **Redaction is deny-by-default and applied at the sink**, not at each call site. Earlier in this
  program an *allowlist* redactor (redact only the fields we thought were sensitive) leaked eight
  real values. Here every string value is scanned for credential shapes and replaced with a shape
  descriptor, and a set of key names is redacted unconditionally regardless of value.
* **Bounded rotation.** A log that can grow without limit becomes the "unrelated logs" the spec
  forbids shipping and a disk-fill hazard. Size-triggered rotation with a fixed keep count.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fsops import extended
from .payload import SECRET_RULES, shannon_bits

#: Key names whose VALUE is never logged, whatever it looks like.
REDACT_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "private_key",
        "credential",
        "credentials",
    }
)

_RES = tuple(re.compile(p) for _, p in SECRET_RULES)

MAX_BYTES = 1 * 1024 * 1024
KEEP = 3
LEVELS = ("debug", "info", "warn", "error")


def redact_text(value: str) -> str:
    """Replace any credential-shaped substring with a shape descriptor. Never echoes the value."""
    out = value
    for rx in _RES:
        out = rx.sub(
            lambda m: (
                f"<redacted:{len(m.group(0))}chars:{shannon_bits(m.group(0)):.1f}bits>"
            ),
            out,
        )
    for token in re.findall(r"[A-Za-z0-9+/=_-]{40,}", out):
        if shannon_bits(token) >= 4.2:
            out = out.replace(
                token, f"<redacted:{len(token)}chars:{shannon_bits(token):.1f}bits>"
            )
    return out


def redact(value: Any, *, key: str | None = None) -> Any:
    """Recursive, deny-by-default redaction over any JSON-shaped value."""
    if key is not None and key.lower() in REDACT_KEYS:
        return "<redacted:key-name>"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


@dataclass
class LogRecord:
    ts: float
    level: str
    op: str
    event: str
    fields: dict[str, Any]

    def as_dict(self) -> dict[str, object]:
        return {
            "ts": round(self.ts, 3),
            "level": self.level,
            "op": self.op,
            "event": self.event,
            "fields": redact(self.fields),
        }


class Logger:
    """Append-only JSONL sink with rotation. Every record passes through ``redact``."""

    def __init__(
        self, path: Path, *, max_bytes: int = MAX_BYTES, keep: int = KEEP
    ) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.keep = keep

    def _rotate_if_needed(self) -> None:
        p = extended(self.path)
        if not p.exists() or p.stat().st_size < self.max_bytes:
            return
        for i in range(self.keep - 1, 0, -1):
            src = self.path.with_suffix(self.path.suffix + f".{i}")
            dst = self.path.with_suffix(self.path.suffix + f".{i + 1}")
            if src.exists():
                os.replace(str(extended(src)), str(extended(dst)))
        os.replace(
            str(p), str(extended(self.path.with_suffix(self.path.suffix + ".1")))
        )

    def log(self, level: str, op: str, event: str, **fields: Any) -> LogRecord:
        if level not in LEVELS:
            raise ValueError(f"unknown log level {level!r}; expected one of {LEVELS}")
        rec = LogRecord(time.time(), level, op, event, dict(fields))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed()
        line = (json.dumps(rec.as_dict(), sort_keys=True) + "\n").encode("utf-8")
        with open(extended(self.path), "ab") as fh:
            fh.write(line)
            fh.flush()
        return rec

    def info(self, op: str, event: str, **f: Any) -> LogRecord:
        return self.log("info", op, event, **f)

    def warn(self, op: str, event: str, **f: Any) -> LogRecord:
        return self.log("warn", op, event, **f)

    def error(self, op: str, event: str, **f: Any) -> LogRecord:
        return self.log("error", op, event, **f)

    def read(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
