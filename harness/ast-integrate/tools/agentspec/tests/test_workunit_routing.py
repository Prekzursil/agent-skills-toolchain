#!/usr/bin/env python3
"""Known rail PASS, unknown rail FAIL. IMP-0135."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2].parent
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentrail"))

from agentspec.spec import Routing  # noqa: E402
from agentrail.rails import load_rails  # noqa: E402
from agentrail.resolve import (  # noqa: E402
    UNKNOWN_RAIL,
    ResolvedRail,
    RoutingViolation,
    resolve_routing,
)


def main() -> int:
    rails = load_rails()
    known = next(iter(rails.values()))
    routing = Routing(vendor=known.vendor, model=known.model, role=known.role)
    got = resolve_routing(routing, rails=rails)
    if not isinstance(got, ResolvedRail):
        print("FAILED known rail", got)
        return 1
    unknown = Routing(vendor="vendor-not-in-rails", model="no-such-model", role="no-such-role")
    bad = resolve_routing(unknown, rails=rails)
    if not isinstance(bad, RoutingViolation) or bad.id != UNKNOWN_RAIL:
        print("FAILED unknown rail", bad)
        return 1
    print("PASS known rail")
    print("PASS unknown rail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
