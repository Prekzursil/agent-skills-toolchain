"""Advisory file leases: conflict is logged, writes still succeed. IMP-0410."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        self._now += float(seconds)
        return self._now


class FileLeaseManager:
    def __init__(self, store: Path | str, clock: Callable[[], float] | None = None):
        self.store = Path(store)
        self.store.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: 0.0)
        self._seq = 0
        self._leases: dict[str, dict] = {}
        self._ttl: dict[str, float] = {}
        self._events: list[dict] = []

    def acquire(self, session_id: str, paths: list[str], ttl_seconds: float = 30.0) -> dict:
        now = float(self.clock())
        self._seq += 1
        lease_id = f"{session_id}-{self._seq}"
        rec = {
            "lease_id": lease_id,
            "session_id": session_id,
            "paths": list(paths),
            "expires_at": now + float(ttl_seconds),
            "ttl_seconds": float(ttl_seconds),
            "ok": True,
        }
        self._leases[lease_id] = rec
        self._ttl[lease_id] = float(ttl_seconds)
        return rec

    def renew(self, session_id: str, lease_id: str) -> dict:
        rec = self._leases[lease_id]
        now = float(self.clock())
        rec["expires_at"] = now + float(rec.get("ttl_seconds") or 10.0)
        rec["ok"] = True
        rec["session_id"] = session_id
        return rec

    def _holders(self, path: str, now: float) -> list[dict]:
        return [
            rec
            for rec in self._leases.values()
            if path in rec["paths"] and float(rec["expires_at"]) > now
        ]

    def note_write(
        self,
        session_id: str,
        path: str,
        payload: bytes = b"",
        dest: Path | str | None = None,
    ) -> dict:
        now = float(self.clock())
        holders = self._holders(path, now)
        conflict = any(h["session_id"] != session_id for h in holders)
        dest_path = Path(dest) if dest is not None else None
        if dest_path is not None:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(payload)
        conflicts = []
        if conflict:
            for h in holders:
                if h["session_id"] != session_id:
                    conflicts.append(
                        {
                            "path": path,
                            "writer_session": session_id,
                            "holder_session": h["session_id"],
                            "lease_id": h.get("lease_id") or h.get("id"),
                            "ts": now,
                        }
                    )
        self._events.extend(conflicts)
        return {
            "ok": True,
            "refused": False,
            "conflict": conflict,
            "conflicts": conflicts,
            "write_succeeded": dest_path is not None and dest_path.is_file(),
            "session_id": session_id,
            "path": path,
            "ts": now,
        }

    def conflict_events(self) -> list[dict]:
        """All lease-conflict events logged by this manager, in order."""
        return list(self._events)

    def active_holders(self, path: str) -> list[dict]:
        """Unexpired leases currently covering ``path``."""
        return [dict(rec) for rec in self._holders(path, float(self.clock()))]
