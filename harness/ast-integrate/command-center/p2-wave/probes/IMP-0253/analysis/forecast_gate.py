"""Forecast admission gate: structured criterion + ISO date, never prose."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Mapping

ADMIT_RESOLVABLE = "ADMIT_RESOLVABLE"
REJECT_MISSING_CRITERION = "REJECT_MISSING_CRITERION"
REJECT_MISSING_RESOLUTION_DATE = "REJECT_MISSING_RESOLUTION_DATE"
REJECT_PROSE_CRITERION = "REJECT_PROSE_CRITERION"
REJECT_UNBOUNDED_HORIZON = "REJECT_UNBOUNDED_HORIZON"
REJECT_NOT_ADMITTED = "REJECT_NOT_ADMITTED"
RESOLVED_TRUE = "RESOLVED_TRUE"
RESOLVED_FALSE = "RESOLVED_FALSE"
TOO_EARLY = "TOO_EARLY"
OBSERVABLE_ABSENT = "OBSERVABLE_ABSENT"


def _iso(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _lookup(obs: Mapping[str, Any], path: str) -> Any:
    if path in obs:
        return obs[path]
    cur: Any = obs
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


@dataclass
class Criterion:
    observable: str = "canary.latency_p99_ms"
    op: str = "<="
    threshold: float = 200.0

    def execute(self, observed: Any) -> bool:
        v = float(observed)
        t = float(self.threshold)
        if self.op == "<=":
            return v <= t
        if self.op == "<":
            return v < t
        if self.op == ">=":
            return v >= t
        if self.op == ">":
            return v > t
        if self.op == "==":
            return v == t
        return False


@dataclass
class Forecast:
    forecast_id: str
    statement: str
    criterion: Criterion | str | None
    resolution_date: str | None
    predicted: bool = True


@dataclass
class SyntheticState:
    as_of: str
    observables: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    admitted: bool = False
    executable: bool = False
    reason: str = ""
    statement_consulted: bool = False
    forecast_id: str = ""
    resolution_date: str | None = None
    resolved: bool = False
    value: bool | None = None
    observed: Any = None
    matches_prediction: bool | None = None
    prose_executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "executable": self.executable,
            "reason": self.reason,
            "statement_consulted": self.statement_consulted,
            "forecast_id": self.forecast_id,
            "resolution_date": self.resolution_date,
            "resolved": self.resolved,
            "value": self.value,
            "observed": self.observed,
            "matches_prediction": self.matches_prediction,
            "prose_executed": self.prose_executed,
        }


def emit(forecast: Forecast) -> Decision:
    d = Decision(forecast_id=forecast.forecast_id, resolution_date=forecast.resolution_date)
    if not forecast.resolution_date:
        d.reason = REJECT_MISSING_RESOLUTION_DATE
        return d
    if str(forecast.resolution_date).lower() in {"never", "unbounded", "infty"}:
        d.reason = REJECT_UNBOUNDED_HORIZON
        return d
    if not _iso(str(forecast.resolution_date)):
        d.reason = REJECT_UNBOUNDED_HORIZON
        return d
    if forecast.criterion is None:
        d.reason = REJECT_MISSING_CRITERION
        return d
    if isinstance(forecast.criterion, str):
        d.reason = REJECT_PROSE_CRITERION
        return d
    d.admitted = True
    d.executable = True
    d.reason = ADMIT_RESOLVABLE
    return d


def emission_fingerprint(decision: Decision) -> str:
    return f"{decision.reason}|{decision.admitted}|{type(decision.resolution_date).__name__}"


class ForecastLibrary:
    def __init__(self) -> None:
        self._ids: list[str] = []

    def try_admit(self, forecast: Forecast) -> Decision:
        d = emit(forecast)
        if d.admitted:
            self._ids.append(forecast.forecast_id)
        return d

    def contains(self, fid: str) -> bool:
        return fid in self._ids

    def admitted_ids(self) -> list[str]:
        return list(self._ids)

    def ids(self) -> tuple[str, ...]:
        return tuple(self._ids)


def resolve(forecast: Forecast, state: SyntheticState) -> Decision:
    gate = emit(forecast)
    d = Decision(
        forecast_id=forecast.forecast_id,
        resolution_date=forecast.resolution_date,
        admitted=gate.admitted,
        executable=gate.executable,
        reason=gate.reason,
    )
    if not gate.admitted:
        d.reason = REJECT_NOT_ADMITTED
        d.prose_executed = False
        return d
    if str(state.as_of) < str(forecast.resolution_date):
        d.reason = TOO_EARLY
        d.resolved = False
        d.value = None
        return d
    crit = forecast.criterion
    assert isinstance(crit, Criterion)
    observed = _lookup(state.observables, crit.observable)
    if observed is None:
        d.reason = OBSERVABLE_ABSENT
        return d
    d.observed = observed
    ok = crit.execute(observed)
    d.resolved = True
    d.value = bool(ok)
    d.reason = RESOLVED_TRUE if ok else RESOLVED_FALSE
    d.matches_prediction = d.value is True if forecast.predicted else d.value is False
    if forecast.predicted:
        d.matches_prediction = d.value is True
    return d
