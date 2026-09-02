"""Heartbeat + byte-growth hang detector."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STALLED = "STALLED"
ALIVE = "ALIVE"
TIMEOUT = "TIMEOUT"


@dataclass
class Verdict:
    state: str
    heartbeat_advanced: bool = False
    byte_growth: bool = False
    slot_released: bool = False
    time_to_classification_s: float | None = None
    unit_id: str = ""
    samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "heartbeat_advanced": self.heartbeat_advanced,
            "byte_growth": self.byte_growth,
            "slot_released": self.slot_released,
            "time_to_classification_s": self.time_to_classification_s,
            "unit_id": self.unit_id,
            "samples": self.samples,
        }


class SlotTracker:
    def __init__(self, capacity: int = 1) -> None:
        self.capacity = int(capacity)
        self._held: set[str] = set()

    def acquire(self, unit_id: str) -> None:
        self._held.add(str(unit_id))

    def release(self, unit_id: str) -> None:
        self._held.discard(str(unit_id))

    def occupied_count(self) -> int:
        return len(self._held)


def catalog_timeout_seconds(catalog: Path, unit_id: str) -> int:
    try:
        data = json.loads(Path(catalog).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 2700
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == unit_id:
            raw = unit.get("timeout_seconds")
            if raw is None:
                raw = (unit.get("timeout") or {}).get("seconds") if isinstance(unit.get("timeout"), dict) else unit.get("timeout")
            if raw is None:
                return 2700
            return int(raw)
    return 2700


def _token(path: Path) -> int:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return int(doc.get("token") or 0)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 0


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def watch(
    hb: Path,
    out: Path,
    timeout_s: float = 4.0,
    stall_window_s: float = 0.28,
    poll_s: float = 0.05,
    unit_id: str = "unit",
    slot: SlotTracker | None = None,
    confirm_alive_s: float | None = None,
    **kwargs: Any,
) -> tuple[Verdict, list[dict[str, Any]]]:
    del kwargs
    if slot is not None:
        slot.acquire(unit_id)
    start = time.monotonic()
    last_hb_change = start
    last_byte_change = start
    prev_tok = _token(Path(hb))
    prev_sz = _size(Path(out))
    hb_adv = False
    byte_adv = False
    samples: list[dict[str, Any]] = []
    deadline = start + float(timeout_s)
    alive_deadline = start + float(confirm_alive_s) if confirm_alive_s else None
    while True:
        now = time.monotonic()
        tok = _token(Path(hb))
        sz = _size(Path(out))
        if tok != prev_tok:
            hb_adv = True
            last_hb_change = now
            prev_tok = tok
        if sz != prev_sz:
            byte_adv = True
            last_byte_change = now
            prev_sz = sz
        samples.append({"t": now - start, "token": tok, "bytes": sz})
        stalled_hb = (now - last_hb_change) >= stall_window_s
        stalled_bytes = (now - last_byte_change) >= stall_window_s
        if stalled_hb and stalled_bytes and (now - start) >= stall_window_s:
            verdict = Verdict(
                state=STALLED,
                heartbeat_advanced=hb_adv,
                byte_growth=byte_adv,
                slot_released=False,
                time_to_classification_s=now - start,
                unit_id=unit_id,
                samples=len(samples),
            )
            # hung fixture never advanced; keep flags false
            if not hb_adv and not byte_adv:
                verdict.heartbeat_advanced = False
                verdict.byte_growth = False
            if slot is not None:
                slot.release(unit_id)
                verdict.slot_released = True
            return verdict, samples
        if alive_deadline is not None and now >= alive_deadline:
            verdict = Verdict(
                state=ALIVE,
                heartbeat_advanced=hb_adv,
                byte_growth=byte_adv,
                slot_released=False,
                time_to_classification_s=now - start,
                unit_id=unit_id,
                samples=len(samples),
            )
            return verdict, samples
        if now >= deadline:
            verdict = Verdict(
                state=TIMEOUT,
                heartbeat_advanced=hb_adv,
                byte_growth=byte_adv,
                slot_released=False,
                time_to_classification_s=now - start,
                unit_id=unit_id,
                samples=len(samples),
            )
            if slot is not None:
                slot.release(unit_id)
                verdict.slot_released = True
            return verdict, samples
        time.sleep(poll_s)
