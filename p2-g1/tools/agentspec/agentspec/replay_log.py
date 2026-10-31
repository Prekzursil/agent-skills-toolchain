"""Record/replay log for fixture work-unit runs. IMP-0144."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FrozenClock:
    def __init__(self, origin: int = 0):
        self.origin = origin
        self._t = origin

    def now(self) -> int:
        self._t += 1
        return self._t


class CountingFakeRail:
    def __init__(self, execute: Callable[..., dict[str, Any]]):
        self._execute = execute
        self.spawns = 0
        self.calls: list[str] = []

    def spawn(self, unit_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.spawns += 1
        self.calls.append(unit_id)
        return self._execute(unit_id, payload)


def fixture_execute(unit_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if unit_id.endswith("fail") or payload.get("force_fail"):
        return {"unit_id": unit_id, "verdict": "FAIL", "reason": "planted"}
    return {"unit_id": unit_id, "verdict": "PASS", "items": payload.get("items") or ["ok"]}


def drop_payload_field(event, field: str, extra: str | None = None):
    if isinstance(event, (bytes, bytearray)):
        log = json.loads(bytes(event).decode("utf-8"))
        kind = field
        key = extra
        for ev in log.get("events") or []:
            if ev.get("kind") == kind or (key and key in (ev.get("payload") or {})):
                payload = dict(ev.get("payload") or {})
                if key:
                    payload.pop(key, None)
                ev["payload"] = payload
        return json.dumps(log, sort_keys=True).encode("utf-8")
    out = dict(event)
    payload = dict(out.get("payload") or {})
    payload.pop(field, None)
    if extra:
        payload.pop(extra, None)
    out["payload"] = payload
    return out


def mutate_producer_items(log_bytes: bytes, drop_index: int = 0, refresh_hash: bool = False, **kwargs: Any) -> bytes:
    log = json.loads(bytes(log_bytes).decode("utf-8"))
    plan = dict(log.get("plan") or {})
    slots = list(plan.get("slots") or [])
    if 0 <= int(drop_index) < len(slots):
        slots.pop(int(drop_index))
    plan["slots"] = slots
    log["plan"] = plan
    events = [e for i, e in enumerate(log.get("events") or []) if i != int(drop_index)]
    log["events"] = events
    if refresh_hash:
        log["value_hash"] = sha256_bytes(json.dumps(plan, sort_keys=True).encode("utf-8"))
    return json.dumps(log, sort_keys=True).encode("utf-8")


@dataclass
class RecordedRun:
    events: list[dict[str, Any]]
    verdicts: list[dict[str, Any]]
    plan: dict[str, Any]
    plan_b: bytes
    verdicts_b: bytes
    log_bytes: bytes
    spawns: int
    run_id: str


@dataclass
class ReplayResult:
    plan_b: bytes
    verdicts_b: bytes
    events: list[dict[str, Any]] = field(default_factory=list)


def record_run(*, rail: CountingFakeRail | None = None, clock: FrozenClock | None = None) -> RecordedRun:
    clock = clock or FrozenClock(0)
    rail = rail or CountingFakeRail(fixture_execute)
    slots = [
        {"unit_id": "IMP-0144-a", "payload": {"items": ["alpha"]}},
        {"unit_id": "IMP-0144-b-fail", "payload": {"force_fail": True}},
        {"unit_id": "IMP-0144-c", "payload": {"items": ["gamma"]}},
    ]
    events: list[dict[str, Any]] = [
        {
            "kind": "run.start",
            "ts": clock.now(),
            "payload": {"params": {"seed": 144}, "debug_note": "non-load-bearing"},
        }
    ]
    verdicts: list[dict[str, Any]] = []
    for slot in slots:
        events.append(
            {
                "kind": "dispatch.recorded",
                "ts": clock.now(),
                "unit_id": slot["unit_id"],
                "payload": dict(slot["payload"]),
            }
        )
        result = rail.spawn(slot["unit_id"], slot["payload"])
        verdicts.append(
            {
                "unit_id": slot["unit_id"],
                "verdict": result.get("verdict"),
                "ts": clock.now(),
            }
        )
    plan = {"run_id": "imp0144-fixture", "slots": slots}
    plan_b = json.dumps(plan, sort_keys=True).encode("utf-8")
    verdicts_b = json.dumps(verdicts, sort_keys=True).encode("utf-8")
    log = {
        "plan": plan,
        "events": events,
        "verdicts": verdicts,
    }
    log_bytes = json.dumps(log, sort_keys=True).encode("utf-8")
    return RecordedRun(
        events=events,
        verdicts=verdicts,
        plan=plan,
        plan_b=plan_b,
        verdicts_b=verdicts_b,
        log_bytes=log_bytes,
        spawns=rail.spawns,
        run_id=plan["run_id"],
    )


def replay_run(log_bytes: bytes, rail: CountingFakeRail | None = None) -> ReplayResult:
    log = json.loads(log_bytes.decode("utf-8"))
    for ev in log.get("events") or []:
        if ev.get("kind") == "run.start":
            payload = ev.get("payload") or {}
            if "params" not in payload:
                raise ValueError("run.start missing load-bearing params")
    if rail is not None:
        # Replay must not spawn even if a rail is supplied.
        pass
    plan_b = json.dumps(log["plan"], sort_keys=True).encode("utf-8")
    verdicts_b = json.dumps(log["verdicts"], sort_keys=True).encode("utf-8")
    result = ReplayResult(plan_b=plan_b, verdicts_b=verdicts_b, events=list(log.get("events") or []))
    result.plan = dict(log.get("plan") or {})  # type: ignore[attr-defined]
    return result


def reconstruct_unverified(log_bytes: bytes) -> ReplayResult:
    log = json.loads(bytes(log_bytes).decode("utf-8"))
    plan = dict(log.get("plan") or {})
    plan_b = json.dumps(plan, sort_keys=True).encode("utf-8")
    verdicts_b = json.dumps(log.get("verdicts") or [], sort_keys=True).encode("utf-8")
    result = ReplayResult(plan_b=plan_b, verdicts_b=verdicts_b, events=list(log.get("events") or []))
    result.plan = plan  # type: ignore[attr-defined]
    return result


def try_replay(log_bytes: bytes, rail: CountingFakeRail | None = None) -> tuple[ReplayResult | None, str | None]:
    try:
        result = replay_run(log_bytes, rail=rail)
        result.plan = json.loads(result.plan_b.decode("utf-8"))  # type: ignore[attr-defined]
        return result, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
