"""Append-only hash-chained event log."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ImmutableRecordError(Exception):
    pass


def _digest(rec: dict[str, Any]) -> str:
    body = {k: rec[k] for k in rec if k != "sha256"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class EventLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._events: list[dict[str, Any]] = []
        self._seq = 0
        self._prev = "0" * 64

    def append(self, event_type: str, payload: dict[str, Any], *, actor_id: str = "") -> dict[str, Any]:
        self._seq += 1
        body = dict(payload)
        rec = {
            "seq": self._seq,
            "event_type": event_type,
            "actor_id": actor_id,
            "payload": body,
            "prev": self._prev,
        }
        rec["sha256"] = _digest(rec)
        self._prev = rec["sha256"]
        self._events.append(rec)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def verify_chain(self) -> None:
        prev = "0" * 64
        for rec in self._events:
            if rec.get("prev") != prev:
                raise ImmutableRecordError("chain-break")
            if rec.get("sha256") != _digest(rec):
                raise ImmutableRecordError("digest-mismatch")
            prev = rec["sha256"]

    def try_rewrite(self, seq: int, new_payload: dict[str, Any], *, actor_id: str = "") -> None:
        self.append(
            "mutation-refused",
            {"op": "rewrite", "seq": seq, "attempt": new_payload},
            actor_id=actor_id,
        )
        raise ImmutableRecordError("rewrite-refused")

    def try_delete(self, seq: int, *, actor_id: str = "") -> None:
        self.append(
            "mutation-refused",
            {"op": "delete", "seq": seq},
            actor_id=actor_id,
        )
        raise ImmutableRecordError("delete-refused")
