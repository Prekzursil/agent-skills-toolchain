"""Blueprint forecast library + named fixture forecasts."""
from __future__ import annotations

from .forecast_gate import Criterion, Forecast, ForecastLibrary, SyntheticState

FORECAST_GOOD = Forecast(
    forecast_id="fx.resolvable",
    statement="canary p99 stays under 200ms by 2027-03-01",
    criterion=Criterion(observable="canary.latency_p99_ms", op="<=", threshold=200.0),
    resolution_date="2027-03-01",
    predicted=True,
)
FORECAST_NO_DATE = Forecast(
    forecast_id="fx.unresolvable-no-date",
    statement=FORECAST_GOOD.statement,
    criterion=FORECAST_GOOD.criterion,
    resolution_date=None,
    predicted=True,
)
STATE_HOLD = SyntheticState(as_of="2027-03-01", observables={"canary": {"latency_p99_ms": 150}})
STATE_MISS = SyntheticState(as_of="2027-03-01", observables={"canary": {"latency_p99_ms": 400}})
STATE_EARLY = SyntheticState(as_of="2026-01-01", observables={"canary": {"latency_p99_ms": 150}})


def build_library():
    lib = ForecastLibrary()
    ids = (
        "bp.morphological-analysis",
        "bp.simulation-counterfactual",
        "bp.forecasting",
        "bp.expert-elicitation",
    )
    rows = []
    for fid in ids:
        d = lib.try_admit(
            Forecast(
                forecast_id=fid,
                statement="blueprint contract",
                criterion=FORECAST_GOOD.criterion,
                resolution_date="2027-03-01",
            )
        )
        rows.append({"id": fid, "ok": d.admitted})
    return lib, rows
