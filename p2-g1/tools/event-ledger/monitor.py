"""Append-only live monitor with fencing tokens (IMP-0225)."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


def _append(path: Path, rec: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


class MonitorDead(RuntimeError):
    """The live monitor process is gone; remote jobs remain on independent files."""


def remote_complete(job_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"job_id": job_id, "status": "complete"}


@dataclass
class LiveMonitor:
    ledger: Path
    run_id: str
    unit_ids: list[str]
    seq: int = 0
    dead: bool = False

    def start_run(self) -> None:
        self._emit({"kind": "run_started", "run_id": self.run_id, "units": list(self.unit_ids)})

    def _emit(self, rec: dict[str, Any]) -> dict[str, Any]:
        self.seq += 1
        rec = dict(rec)
        rec["seq"] = self.seq
        rec["run_id"] = self.run_id
        _append(self.ledger, rec)
        return rec

    def dispatch(self, unit_id: str) -> dict[str, Any]:
        token = f"{self.run_id}:{unit_id}:{self.seq + 1}"
        rec = self._emit(
            {"kind": "unit_dispatched", "unit_id": unit_id, "fencing_token": token}
        )
        return rec

    def harvest(self, unit_id: str, receipt_hash: str) -> dict[str, Any]:
        return self._emit(
            {
                "kind": "unit_harvested",
                "unit_id": unit_id,
                "receipt_hash": receipt_hash,
            }
        )

    def snapshot(self) -> dict[str, Any]:
        from recover import rebuild

        return rebuild(self.ledger).canonical()

    def kill(self) -> None:
        self.dead = True

    def record_monitor_died(self) -> None:
        self._emit({"kind": "monitor_died"})
        self.dead = True


def remote_complete(
    ledger: Path,
    run_id: str,
    unit_id: str,
    receipt_hash: str,
    fencing_token: str,
) -> dict[str, Any]:
    rec = {
        "kind": "remote_complete",
        "run_id": run_id,
        "unit_id": unit_id,
        "receipt_hash": receipt_hash,
        "fencing_token": fencing_token,
    }
    rows = _load(Path(ledger))
    seq = max((r.get("seq") or 0) for r in rows) if rows else 0
    rec["seq"] = seq + 1
    _append(Path(ledger), rec)
    return rec
