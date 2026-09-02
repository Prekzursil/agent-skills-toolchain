"""Shared 200-unit synthetic fan-out for IMP-0220 probes."""

from __future__ import annotations

import ast
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parents[3]
AGENTSPEC_ROOT = REPO / "tools" / "agentspec"
if str(AGENTSPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTSPEC_ROOT))

from agentspec.clock import FakeClock  # noqa: E402
from agentspec.stagger_admission import (  # noqa: E402
    RailPolicy,
    StaggeredAdmissionScheduler,
    UnknownRailError,
    histogram_matches_stagger,
    interarrival_histogram,
    is_burst,
)

UNIT_ID = "IMP-0220"
N_UNITS = 200
RAILS = ("anthropic", "openai", "google", "local")
STAGGER_INTERVAL_S = 0.05
WALL_BUDGET_S = 1.0
SCHEDULER_SRC = REPO / "tools" / "agentspec" / "agentspec" / "stagger_admission.py"


def cohort(n: int = N_UNITS) -> list[tuple[str, str]]:
    return [(f"U-{i:04d}", RAILS[i % len(RAILS)]) for i in range(n)]


def policies(
    *,
    interval_s: float = STAGGER_INTERVAL_S,
    rate_per_s: float | None = None,
) -> dict[str, RailPolicy]:
    return {
        rail: RailPolicy(
            rail_id=rail,
            stagger_interval_s=interval_s,
            rate_per_s=rate_per_s,
        )
        for rail in RAILS
    }


def run_fanout(
    *,
    stagger_enabled: bool,
    n: int = N_UNITS,
    rate_per_s: float | None = None,
    interval_s: float = STAGGER_INTERVAL_S,
) -> dict:
    clock = FakeClock(0.0)
    sched = StaggeredAdmissionScheduler(
        clock,
        policies(interval_s=interval_s, rate_per_s=rate_per_s),
        stagger_enabled=stagger_enabled,
    )
    wall0 = time.monotonic()
    events = sched.admit_fanout(cohort(n))
    wall_s = time.monotonic() - wall0
    hist = interarrival_histogram(events, per_rail=True)
    return {
        "stagger_enabled": stagger_enabled,
        "n": n,
        "interval_s": interval_s,
        "rate_per_s": rate_per_s,
        "clock_now": clock.now(),
        "sleep_calls": len(clock.sleep_calls),
        "wall_s": wall_s,
        "hist": hist,
        "matches_stagger": histogram_matches_stagger(hist, interval_s),
        "burst": is_burst(hist),
        "unknown_rail_named": _unknown_rail_named(sched),
        "events": [
            {
                "unit_id": e.unit_id,
                "rail_id": e.rail_id,
                "admitted_at": e.admitted_at,
                "waited_s": e.waited_s,
            }
            for e in events
        ],
    }


def _unknown_rail_named(sched: StaggeredAdmissionScheduler) -> bool:
    try:
        sched.admit("U-UNKNOWN", "not-a-rail")
    except UnknownRailError as exc:
        return str(exc) == "unknown-rail:not-a-rail" and exc.rail_id == "not-a-rail"
    return False


def forbid_wall_clock_in_scheduler() -> list[str]:
    """Static check: stagger_admission.py must not call time.time / time.sleep / datetime.now."""
    src = SCHEDULER_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(SCHEDULER_SRC))
    hits: list[str] = []
    time_names: set[str] = set()
    dt_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "time":
                    time_names.add(alias.asname or "time")
                if alias.name == "datetime":
                    dt_names.add(alias.asname or "datetime")
        elif isinstance(node, ast.ImportFrom) and node.module == "time":
            for alias in node.names:
                if alias.name in {"time", "sleep", "monotonic", "perf_counter"}:
                    hits.append(f"from-time-import:{alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module == "datetime":
            hits.append("from-datetime-import")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in time_names and node.attr in {
                "time",
                "sleep",
                "monotonic",
                "perf_counter",
            }:
                hits.append(f"time.{node.attr}:L{node.lineno}")
            if node.value.id in dt_names and node.attr in {"now", "utcnow"}:
                hits.append(f"datetime.{node.attr}:L{node.lineno}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"time", "sleep"}:
                hits.append(f"bare-{node.func.id}:L{node.lineno}")
    return hits
