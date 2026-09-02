"""Deterministic HTTP mock: 429 with Retry-After, 529 overload, then 200."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from clock import VirtualClock


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""


@dataclass(frozen=True)
class RequestEvent:
    t: float
    unit_id: str
    worker_id: str
    status: int
    headers: dict[str, str]


def _as_response(item: Response | int | tuple[int, dict[str, str]]) -> Response:
    if isinstance(item, Response):
        return item
    if isinstance(item, int):
        return Response(item, {})
    status, headers = item
    return Response(int(status), dict(headers))


class MockLimiter:
    """Per-worker response scripts. Duplicate workers get an independent copy."""

    def __init__(self, clock: VirtualClock) -> None:
        self.clock = clock
        self.unit_plans: dict[str, list[Response]] = {}
        self._remaining: dict[str, list[Response]] = {}
        self.events: list[RequestEvent] = []

    def set_plan(
        self, unit_id: str, items: Sequence[Response | int | tuple[int, dict[str, str]]]
    ) -> None:
        self.unit_plans[unit_id] = [_as_response(x) for x in items]

    def request(self, unit_id: str, worker_id: str) -> Response:
        if worker_id not in self._remaining:
            plan = self.unit_plans.get(unit_id) or [Response(200, {})]
            self._remaining[worker_id] = list(plan)
        queue = self._remaining[worker_id]
        resp = queue.pop(0) if queue else Response(200, {})
        self.events.append(
            RequestEvent(
                t=self.clock.now,
                unit_id=unit_id,
                worker_id=worker_id,
                status=resp.status,
                headers=dict(resp.headers),
            )
        )
        return resp

    def timeline(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for ev in self.events:
            rows.append(
                {
                    "t": ev.t,
                    "unit_id": ev.unit_id,
                    "worker_id": ev.worker_id,
                    "status": ev.status,
                    "headers": dict(ev.headers),
                }
            )
        return rows
