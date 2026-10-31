"""Local-only telemetry sink (IMP-0057).

Records stay on disk. Nothing here opens a socket. Events are sanitized
before write so a later opt-in transport cannot pick up prompts, paths,
or file contents from the log.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from privacy import POSTURE_LOCAL_ONLY, sanitize_event

ALLOWED_LOCAL_FIELDS = frozenset(
    {
        "event",
        "timestamp",
        "unit_id",
        "posture",
        "result",
        "code",
        "command",
        "ok",
    }
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LocalSink:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: Mapping[str, Any]) -> dict[str, Any]:
        cleaned = sanitize_event(event)
        record = {k: v for k, v in cleaned.items() if k in ALLOWED_LOCAL_FIELDS}
        record.setdefault("timestamp", _utc())
        record.setdefault("posture", POSTURE_LOCAL_ONLY)
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
        return record
