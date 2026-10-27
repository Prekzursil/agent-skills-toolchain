"""Plugin health aggregate: blocked/unrun/throwing probes prevent HEALTHY."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class HealthContext:
    root: Path
    force_state: dict[str, str] = field(default_factory=dict)


@dataclass
class ProbeResult:
    probe_id: str
    state: str
    reason: str = ""
    evidence: dict = field(default_factory=dict)


@dataclass
class BothStatesControl:
    unit_id: str
    known_good: str
    known_broken: str
    expected_good: str
    expected_broken: str
    plant_good: Callable
    plant_broken: Callable


@dataclass
class HealthReport:
    healthy: bool
    aggregate: str
    probes: list[ProbeResult]
    blocked_ids: list[str]
    missing_unrun: list[str]
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "aggregate": self.aggregate,
            "probes": [
                {"probe_id": p.probe_id, "state": p.state, "reason": p.reason}
                for p in self.probes
            ],
            "blocked_ids": list(self.blocked_ids),
            "missing_unrun": list(self.missing_unrun),
            "reason": self.reason,
        }


class Probe:
    probe_id = "unnamed"

    def run(self, ctx: HealthContext) -> ProbeResult:
        return ProbeResult(self.probe_id, "SUCCESS")


class Registry(list):
    def register(self, probe: Any) -> None:
        self.append(probe)

    def require_both_states(self) -> list[Any]:
        return [p for p in self if getattr(p, "both_states", None) is not None]


def default_registry() -> Registry:
    from health_probes import default_probes

    return Registry(default_probes())


def aggregate(registry: list[Any], rows: list[ProbeResult]) -> HealthReport:
    ids = [getattr(p, "probe_id", None) for p in registry]
    seen = {r.probe_id for r in rows}
    unrun = [i for i in ids if i and i not in seen]
    healthy = bool(rows) and all(r.state == "SUCCESS" for r in rows) and not unrun
    return HealthReport(
        healthy=healthy,
        aggregate="HEALTHY" if healthy else "NOT-HEALTHY",
        probes=list(rows),
        blocked_ids=[r.probe_id for r in rows if r.state == "BLOCKED"],
        missing_unrun=unrun,
        reason="unrun" if unrun else ("ok" if healthy else "failed"),
    )


def run_all(registry: list[Any], ctx: HealthContext) -> HealthReport:
    results: list[ProbeResult] = []
    blocked: list[str] = []
    for probe in registry:
        pid = getattr(probe, "probe_id", None) or probe.__class__.__name__
        forced = (ctx.force_state or {}).get(pid)
        if forced:
            row = ProbeResult(pid, forced, reason="forced")
            results.append(row)
            if forced == "BLOCKED":
                blocked.append(pid)
            continue
        try:
            row = probe.run(ctx)
            if not isinstance(row, ProbeResult):
                row = ProbeResult(pid, str(getattr(row, "state", "SUCCESS")))
            row.probe_id = pid
        except Exception as exc:
            row = ProbeResult(
                pid, "FAILED", reason=str(exc), evidence={"uncaught": True}
            )
        results.append(row)
        if row.state == "BLOCKED":
            blocked.append(pid)
    unrun = []
    healthy = (
        bool(results)
        and not blocked
        and not unrun
        and all(r.state == "SUCCESS" for r in results)
    )
    aggregate = "HEALTHY" if healthy else "NOT-HEALTHY"
    reason = "ok" if healthy else ("blocked=" + ",".join(blocked) if blocked else "failed")
    return HealthReport(
        healthy=healthy,
        aggregate=aggregate,
        probes=results,
        blocked_ids=blocked,
        missing_unrun=unrun,
        reason=reason,
    )
