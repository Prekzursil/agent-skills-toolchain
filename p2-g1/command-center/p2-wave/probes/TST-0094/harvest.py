#!/usr/bin/env python3
"""TST-0094 typed remote harvest.

RemoteHarvest.harvest(session_id) returns ONE OF four typed outcomes -
never a shared empty:
  HARVESTED          connected, filter matched, delta > 0 (rc 0)
  NOTHING_TO_HARVEST connected, filter matched, delta = 0 (rc 1)
  FILTER_MISMATCH    filter key present but matched nothing (rc 2)
  CONNECTION_FAILURE substrate unreachable (rc 3)
reject_filter_key(value) raises NullFilterKeyError for None/empty at
WRITE time - a null session_id can never hide results (the receipt's
measured analogue)."""
from __future__ import annotations

from typing import Any

OUTCOME_RC = {"HARVESTED": 0, "NOTHING_TO_HARVEST": 1, "FILTER_MISMATCH": 2, "CONNECTION_FAILURE": 3}


class NullFilterKeyError(ValueError):
    pass


class RemoteSubstrate:
    def __init__(self, session_id: str | None, artifacts: list[dict], connected: bool = True,
                 filter_matches: bool = True) -> None:
        self.session_id = session_id
        self.artifacts = list(artifacts)
        self.connected = connected
        self.filter_matches = filter_matches

    def read(self) -> list[dict] | None:
        return list(self.artifacts) if self.connected else None


def reject_filter_key(value: Any) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise NullFilterKeyError("null/empty filter key would hide every result - rejected at write time")


class RemoteHarvest:
    def __init__(self, substrate: RemoteSubstrate, local_store: set[str] | None = None) -> None:
        self.substrate = substrate
        self.local_store = local_store if local_store is not None else set()

    def harvest(self, session_id: str | None, filter_key: str = "session_id") -> dict:
        reject_filter_key(session_id)
        payload = self.substrate.read()
        if payload is None:
            return self._emit("CONNECTION_FAILURE", session_id, "substrate unreachable", [], 0)
        if not self.substrate.filter_matches:
            return self._emit("FILTER_MISMATCH", session_id, "filter matched zero sessions", [], 0)
        seen = [a for a in payload if a.get("session_id") == session_id]
        new = [a for a in seen if a["id"] not in self.local_store]
        for a in new:
            self.local_store.add(a["id"])
        if seen and not new:
            return self._emit("NOTHING_TO_HARVEST", session_id, "session exists and filter matched; remote produced zero new artifacts", [], 0)
        if new:
            return self._emit("HARVESTED", session_id, "transferred " + str(len(new)) + " new artifact(s)", new, len(new))
        return self._emit("FILTER_MISMATCH", session_id, "session unknown to the remote filter", [], 0)

    def _emit(self, outcome: str, session_id: Any, reason: str, arts: list[dict], delta: int) -> dict:
        return {"outcome": outcome, "exit_code": OUTCOME_RC[outcome], "session_id": session_id,
                "reason": reason, "artifact_ids": [a["id"] for a in arts],
                "transferred": len(arts), "new_artifact_delta": delta, "empty_result": False}


class CollapsingMutantHarvest:
    """The recorded defect shape: every empty-looking run -> shared EMPTY."""

    def harvest(self, session_id: str | None, filter_key: str = "session_id") -> dict:
        try:
            self.substrate.read()  # type: ignore[attr-defined]
            return {"outcome": "EMPTY", "exit_code": 0, "session_id": session_id,
                    "reason": "nothing to report", "artifact_ids": [], "transferred": 0,
                    "new_artifact_delta": 0, "empty_result": True}
        except Exception:
            return {"outcome": "EMPTY", "exit_code": 0, "session_id": session_id,
                    "reason": "nothing to report", "artifact_ids": [], "transferred": 0,
                    "new_artifact_delta": 0, "empty_result": True}
