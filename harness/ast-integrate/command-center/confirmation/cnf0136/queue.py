"""Confirmation queue store. Re-queue updates in place; never inserts a twin."""
from __future__ import annotations

from typing import Any


class VerdictLaunderingError(RuntimeError):
    """A claim already REFUTED cannot be rewritten as CONFIRMED."""


class RecordStore:
    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []

    def upsert(self, rec: dict[str, Any]) -> dict[str, Any]:
        rid = str(rec["record_id"])
        if rid in self._by_id:
            self._by_id[rid] = rec
        else:
            self._by_id[rid] = rec
            self._order.append(rid)
        return rec

    def get(self, rid: str) -> dict[str, Any] | None:
        return self._by_id.get(rid)

    def count(self) -> int:
        return len(self._order)

    def records(self) -> list[dict[str, Any]]:
        return [self._by_id[i] for i in self._order]
