"""In-memory decision ledger keyed by change_id."""
from __future__ import annotations

from typing import Any, Mapping


class DecisionLedger:
    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}

    def record(self, decision: Mapping[str, Any]) -> None:
        key = str(decision.get("change_id") or decision.get("commit_sha") or "")
        self._rows[key] = dict(decision)
        sha = decision.get("commit_sha")
        if sha:
            self._rows[str(sha)] = dict(decision)

    def get(self, change_id: str) -> dict[str, Any] | None:
        return self._rows.get(str(change_id))
