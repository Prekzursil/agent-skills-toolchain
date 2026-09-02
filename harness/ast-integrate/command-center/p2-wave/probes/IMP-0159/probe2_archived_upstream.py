#!/usr/bin/env python3
"""Probe 2: archived-upstream flagged; maintained twin not (both-states).

The cached maintenance record is still fresh, so the scheduler must flag
from the cache and must not call the network transport. A ForbiddenTransport
fails the probe if any fetch is attempted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

from candidates.freshness import (  # noqa: E402
    CacheStaleNoTransport,
    ForbiddenTransport,
    InjectedClock,
    flag_as_dict,
    flag_maintenance,
)

FORBIDDEN_IMPORT_TOKENS = (
    "import socket",
    "from socket",
    "import urllib",
    "from urllib",
    "import http.client",
    "from http",
    "import requests",
    "from requests",
    "import aiohttp",
    "from aiohttp",
)


def main() -> int:
    src = (REPO / "tools" / "candidates" / "freshness.py").read_text(encoding="utf-8")
    leaked = [tok for tok in FORBIDDEN_IMPORT_TOKENS if tok in src]
    if leaked:
        print(f"FAILED:IMP-0159-probe2 scheduler imports network stack {leaked}")
        return 1

    rows = S.load_candidates()
    table = S.ttl_policy()
    transport = ForbiddenTransport()
    flags = flag_maintenance(rows, S.CLOCK_WITHIN, table, transport)
    by_id = {item.candidate_id: item for item in flags}
    archived = by_id[S.ARCHIVED_ID]
    maintained = by_id[S.MAINTAINED_ID]
    subject = by_id[S.TTL_SUBJECT]

    stale_clock = InjectedClock(S.T0 + table.classes["maintenance-cache"] + 1)
    stale_raised = False
    try:
        flag_maintenance(rows, stale_clock, table, transport=None)
    except CacheStaleNoTransport:
        stale_raised = True

    checks = {
        "archived_flagged": archived.flagged is True and archived.archived is True,
        "maintained_not_flagged": maintained.flagged is False and maintained.archived is False,
        "fresh_cache_no_network": (
            archived.network_called is False
            and maintained.network_called is False
            and subject.network_called is False
            and archived.cache_fresh is True
            and maintained.cache_fresh is True
        ),
        "transport_never_called": transport.calls == [],
        "both_states": archived.flagged is True and maintained.flagged is False,
        "stale_cache_fail_closed_without_transport": stale_raised,
        "stale_did_not_call_transport": transport.calls == [],
        "no_network_imports": leaked == [],
    }
    payload = {
        "probe": "probe2-archived-upstream",
        "unit_id": "IMP-0159",
        "clock_within": S.CLOCK_WITHIN.now_unix,
        "archived": flag_as_dict(archived),
        "maintained": flag_as_dict(maintained),
        "transport_calls": list(transport.calls),
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(payload, sort_keys=True))
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print(f"FAILED:IMP-0159-probe2 {failed}")
        return 1
    print(
        "SUCCESS:IMP-0159-probe2 archived flagged, maintained silent, "
        "network_calls=0 on fresh cache"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
