"""Remote runtime job list: a store independent of the monitor ledger.

Signal (b) in TST-0150: after monitor death, the remote side is queried by
re-reading this file from disk. The monitor process never owns this path.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"

TERMINAL = frozenset({STATUS_SUCCEEDED, STATUS_FAILED})


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(path)


def load_jobs(path: Path) -> dict[str, Any]:
    """Read the remote job list FROM DISK. Callers must not pass an in-memory map."""
    if not path.is_file():
        return {"jobs": {}}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        raise ValueError(f"remote job list is not an object with jobs: {path}")
    return doc


class RemoteRuntime:
    """Durable job table owned by the remote worker, not the monitor."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            _atomic_write(self.path, {"jobs": {}})

    def mark_running(self, unit_id: str, fencing_token: int | None = None) -> None:
        doc = load_jobs(self.path)
        doc["jobs"][unit_id] = {
            "unit_id": unit_id,
            "status": STATUS_RUNNING,
            "fencing_token": fencing_token,
            "receipt_hash": None,
        }
        _atomic_write(self.path, doc)

    def finish(
        self,
        unit_id: str,
        receipt_hash: str,
        *,
        status: str = STATUS_SUCCEEDED,
        fencing_token: int | None = None,
    ) -> None:
        if status not in TERMINAL:
            raise ValueError(f"finish requires a terminal status, got {status}")
        doc = load_jobs(self.path)
        prev = doc["jobs"].get(unit_id) or {}
        token = fencing_token if fencing_token is not None else prev.get("fencing_token")
        doc["jobs"][unit_id] = {
            "unit_id": unit_id,
            "status": status,
            "fencing_token": token,
            "receipt_hash": receipt_hash,
        }
        _atomic_write(self.path, doc)

    def query_from_disk(self) -> dict[str, Any]:
        return load_jobs(self.path)
