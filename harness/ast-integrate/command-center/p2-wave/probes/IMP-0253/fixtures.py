"""Both-states fixtures for IMP-0253 probes and the receipt emitter.

The resolvable and unresolvable forecasts share the same statement so a
gate that scored prose would not discriminate. Discrimination is the
presence of an ISO resolution date plus a structured criterion.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
_CC = _REPO / "command-center"
if str(_CC) not in sys.path:
    sys.path.insert(0, str(_CC))

from analysis.forecast_gate import (  # noqa: E402
    Criterion,
    Forecast,
    SyntheticState,
)
from analysis.library import (  # noqa: E402
    FORECAST_GOOD,
    FORECAST_NO_DATE,
    STATE_EARLY,
    STATE_HOLD,
    STATE_MISS,
)

RESOLVABLE = FORECAST_GOOD
UNRESOLVABLE_NO_DATE = FORECAST_NO_DATE

UNRESOLVABLE_PROSE = replace(
    RESOLVABLE,
    forecast_id="fx.unresolvable-prose",
    criterion="we'll know it when leadership agrees it feels right",
)

UNRESOLVABLE_UNBOUNDED = replace(
    RESOLVABLE,
    forecast_id="fx.unresolvable-never",
    resolution_date="never",
)

UNRESOLVABLE_NO_CRIT = replace(
    RESOLVABLE,
    forecast_id="fx.unresolvable-no-criterion",
    criterion=None,
)

PROSE_STATEMENT_SWAP = replace(
    RESOLVABLE,
    statement="utterly different marketing copy that claims the opposite",
)

HOLD = STATE_HOLD
MISS = STATE_MISS
EARLY = STATE_EARLY

# Nested vs flat observable must resolve the same number.
HOLD_FLAT = SyntheticState(
    as_of="2027-03-01",
    observables={"canary.latency_p99_ms": 150},
)


def criterion() -> Criterion:
    crit = RESOLVABLE.criterion
    assert isinstance(crit, Criterion)
    return crit
