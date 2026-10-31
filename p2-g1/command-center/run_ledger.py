"""Append-only run-state ledger with idempotent completed records (IMP-0443)."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _as_bytes(raw: bytes | str) -> bytes:
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return raw


def split_complete_lines(raw: bytes | str) -> tuple[list[bytes], bytes | None]:
    data = _as_bytes(raw).replace(b"\r\n", b"\n")
    parts = data.split(b"\n")
    bodies: list[bytes] = []
    incomplete: bytes | None = None
    for i, part in enumerate(parts):
        if part == b"" and i == len(parts) - 1:
            continue
        try:
            json.loads(part.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            incomplete = part
            continue
        bodies.append(part)
    return bodies, incomplete


def read_records(path: Path | str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return []
    bodies, _incomplete = split_complete_lines(p.read_bytes())
    out: list[dict[str, Any]] = []
    for body in bodies:
        rec = json.loads(body.decode("utf-8"))
        if isinstance(rec, dict):
            out.append(rec)
    return out


def append_record(path: Path | str, rec: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n"
    with p.open("ab") as fh:
        fh.write(line.encode("utf-8"))
        fh.flush()


def executed_multiset(recs: list[dict[str, Any]] | None) -> dict[str, int]:
    ids = [str(r.get("unit_id") or "") for r in (recs or []) if r.get("kind") == "completed"]
    ids = [i for i in ids if i]
    return dict(Counter(ids))


def duplicate_ids(multi: Any) -> list[str]:
    if hasattr(multi, "items"):
        return [str(k) for k, v in multi.items() if int(v or 0) > 1]
    return []


class RunLedger:
    def __init__(self, path: Path | str, run_id: str | None = None) -> None:
        self.path = Path(path)
        self.run_id = run_id or "run"
        existing = read_records(self.path)
        self._seq = max((int(r.get("seq") or 0) for r in existing), default=0)

    def _stamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def completed_set(self) -> set[str]:
        return {
            str(r.get("unit_id") or "")
            for r in read_records(self.path)
            if r.get("kind") == "completed" and r.get("unit_id")
        }

    def pending(self, catalog: list[str]) -> list[str]:
        done = self.completed_set()
        return [str(u) for u in catalog if str(u) not in done]

    def record_started(self, unit_id: str) -> dict[str, Any]:
        rec = {
            "seq": self._next_seq(),
            "kind": "started",
            "unit_id": str(unit_id),
            "run_id": self.run_id,
            "ts": self._stamp(),
        }
        append_record(self.path, rec)
        return rec

    def record_completed(self, unit_id: str, allow_duplicate: bool = False) -> dict[str, Any] | None:
        uid = str(unit_id)
        if not allow_duplicate and uid in self.completed_set():
            return None
        rec = {
            "seq": self._next_seq(),
            "kind": "completed",
            "unit_id": uid,
            "run_id": self.run_id,
            "ts": self._stamp(),
        }
        append_record(self.path, rec)
        return rec


__all__ = [
    "RunLedger",
    "append_record",
    "duplicate_ids",
    "executed_multiset",
    "read_records",
    "split_complete_lines",
]
