"""Durable remainder ledger: resume continues leftover budget, never reloads caps.

TST-0170 SUT. Catalog input tools/lib/handled-ledger.mjs is an idempotency
ledger (handled keys) and has no retry/token/wall-clock axes, so this module
is the live remainder surface the named probes actually drive.

Invariant: remaining[axis] + consumed[axis] == caps[axis] after every op.
resume() copies the suspended remainder; it must not assign caps[axis].
tally_consumed() sums consume-event deltas, not snapshot.consumed.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

AXES = ("retries", "tokens", "wall_clock_ms")
SCHEMA = "resume-budget-ledger/v1"


class ResumeBudgetError(RuntimeError):
    """Ledger contract violation."""


def remainders_equal(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    try:
        return all(int(left[axis]) == int(right[axis]) for axis in AXES)
    except (KeyError, TypeError, ValueError):
        return False


def last_suspend_remaining(events: list[dict], run_id: str) -> dict[str, int] | None:
    for event in reversed(events):
        if event.get("run_id") == run_id and event.get("op") == "suspend":
            remaining = event.get("remaining")
            return deepcopy(remaining) if isinstance(remaining, dict) else None
    return None


def resume_event_remaining(events: list[dict], run_id: str) -> dict[str, int] | None:
    for event in reversed(events):
        if event.get("run_id") == run_id and event.get("op") == "resume":
            remaining = event.get("remaining")
            return deepcopy(remaining) if isinstance(remaining, dict) else None
    return None


def _int_axes(src: dict, *, allow_missing: bool = False) -> dict[str, int]:
    out: dict[str, int] = {}
    for axis in AXES:
        if axis not in src:
            if allow_missing:
                continue
            raise ResumeBudgetError(f"missing-axis:{axis}")
        value = int(src[axis])
        if value < 0:
            raise ResumeBudgetError(f"negative-axis:{axis}")
        out[axis] = value
    return out


def _atomic_write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


class ResumeBudgetLedger:
    """JSON file ledger. One writer. Resume never refills remaining from caps."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._doc: dict[str, Any] = {
            "schema": SCHEMA,
            "runs": {},
            "events": [],
        }
        if self.path.is_file():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ResumeBudgetError("ledger-not-object")
        runs = raw.get("runs")
        events = raw.get("events")
        if not isinstance(runs, dict) or not isinstance(events, list):
            raise ResumeBudgetError("ledger-shape")
        self._doc = {
            "schema": str(raw.get("schema") or SCHEMA),
            "runs": runs,
            "events": events,
        }

    def _persist(self) -> None:
        _atomic_write_json(self.path, self._doc)

    def _require(self, run_id: str) -> dict[str, Any]:
        run = self._doc["runs"].get(run_id)
        if not isinstance(run, dict):
            raise ResumeBudgetError(f"unknown-run:{run_id}")
        return run

    def _event(self, op: str, run_id: str, run: dict[str, Any], **extra: Any) -> None:
        rec = {
            "op": op,
            "run_id": run_id,
            "status": run.get("status"),
            "remaining": deepcopy(run["remaining"]),
            "consumed": deepcopy(run["consumed"]),
        }
        rec.update(deepcopy(extra))
        self._doc["events"].append(rec)

    def create(self, run_id: str, caps: dict[str, int]) -> dict[str, Any]:
        rid = str(run_id).strip()
        if not rid:
            raise ResumeBudgetError("empty-run-id")
        if rid in self._doc["runs"]:
            raise ResumeBudgetError(f"duplicate-run:{rid}")
        declared = _int_axes(caps)
        run = {
            "run_id": rid,
            "status": "running",
            "caps": declared,
            "remaining": deepcopy(declared),
            "consumed": {axis: 0 for axis in AXES},
        }
        self._doc["runs"][rid] = run
        self._event("create", rid, run)
        self._persist()
        return deepcopy(run)

    def consume(self, run_id: str, delta: dict[str, int]) -> dict[str, Any]:
        run = self._require(run_id)
        if run["status"] != "running":
            raise ResumeBudgetError(f"consume-not-running:{run['status']}")
        spent = _int_axes(delta)
        for axis in AXES:
            if run["remaining"][axis] < spent[axis]:
                raise ResumeBudgetError(f"over-cap:{axis}")
            run["remaining"][axis] -= spent[axis]
            run["consumed"][axis] += spent[axis]
        self._event("consume", run_id, run, delta=spent)
        self._persist()
        return deepcopy(run)

    def suspend(self, run_id: str) -> dict[str, Any]:
        run = self._require(run_id)
        if run["status"] != "running":
            raise ResumeBudgetError(f"suspend-not-running:{run['status']}")
        run["status"] = "suspended"
        self._event("suspend", run_id, run)
        self._persist()
        return deepcopy(run)

    def resume(self, run_id: str) -> dict[str, Any]:
        """Continue the suspended remainder. Caps are never copied onto remaining."""
        run = self._require(run_id)
        if run["status"] != "suspended":
            raise ResumeBudgetError(f"resume-not-suspended:{run['status']}")
        # Deliberate: do not `run["remaining"] = deepcopy(run["caps"])`.
        run["status"] = "running"
        self._event("resume", run_id, run)
        self._persist()
        return deepcopy(run)

    def snapshot(self, run_id: str) -> dict[str, Any]:
        return deepcopy(self._require(run_id))

    def events(self, run_id: str | None = None) -> list[dict[str, Any]]:
        rows = self._doc["events"]
        if run_id is None:
            return deepcopy(rows)
        return [deepcopy(event) for event in rows if event.get("run_id") == run_id]

    def tally_consumed(self, run_id: str) -> dict[str, int]:
        total = {axis: 0 for axis in AXES}
        for event in self._doc["events"]:
            if event.get("run_id") != run_id or event.get("op") != "consume":
                continue
            delta = event.get("delta") or {}
            for axis in AXES:
                total[axis] += int(delta[axis])
        return total
