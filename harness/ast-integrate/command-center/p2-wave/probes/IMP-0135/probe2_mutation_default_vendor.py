#!/usr/bin/env python3
"""Probe 2: hardcode a vendor default in the resolver; unknown-rail test goes red."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Mapping, Union

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentrail"))

from agentspec.spec import Routing  # noqa: E402
from agentrail.rails import RailRecord, load_rails  # noqa: E402
from agentrail.resolve import (  # noqa: E402
    UNKNOWN_RAIL,
    ResolvedRail,
    RoutingViolation,
    match_rail,
    resolve_routing,
)

UNKNOWN = Routing(
    vendor="vendor-not-in-rails",
    model="no-such-model",
    role="no-such-role",
)
RESOLVE_PY = REPO / "tools" / "agentrail" / "agentrail" / "resolve.py"


def mutant_resolve_routing(
    routing: Routing,
    *,
    rails: Mapping[str, RailRecord] | None = None,
) -> Union[ResolvedRail, RoutingViolation]:
    """Same as resolve_routing, but a miss silently takes the first rails.toml row."""
    table = rails if rails is not None else load_rails()
    record = match_rail(table, routing)
    if record is None:
        record = next(iter(table.values()))  # MUTANT: silent vendor default
    return ResolvedRail(
        name=record.name,
        vendor=record.vendor,
        model=record.model,
        role=record.role,
        fallbacks=tuple(routing.fallbacks),
    )


def _unknown_must_fail(resolver) -> None:
    result = resolver(UNKNOWN)
    assert isinstance(result, RoutingViolation), result
    assert result.id == UNKNOWN_RAIL, result


def main() -> int:
    src = RESOLVE_PY.read_text(encoding="utf-8")
    if "unknown_rail_violation" not in src or "must not substitute a hardcoded vendor" not in src:
        print("FAILED:IMP-0135-probe2 live resolver lost the fail-closed unknown-rail path")
        return 1

    _unknown_must_fail(resolve_routing)

    mutant_red = False
    try:
        _unknown_must_fail(mutant_resolve_routing)
    except AssertionError:
        mutant_red = True

    mutant_result = mutant_resolve_routing(UNKNOWN)
    mutant_silent = isinstance(mutant_result, ResolvedRail)
    live_after = resolve_routing(UNKNOWN)
    live_still_fails = (
        isinstance(live_after, RoutingViolation) and live_after.id == UNKNOWN_RAIL
    )

    print(
        f"live_unknown_fails={live_still_fails} "
        f"mutant_test_red={mutant_red} "
        f"mutant_silent_default={mutant_silent} "
        f"mutant_vendor={getattr(mutant_result, 'vendor', None)}"
    )
    if not (live_still_fails and mutant_red and mutant_silent):
        print("FAILED:IMP-0135-probe2 mutation did not turn the unknown-rail test red")
        return 1
    print(
        "SUCCESS:IMP-0135-probe2 hardcoded vendor default turns unknown-rail test red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
