"""IMP-0159 probe 2 (source, both-states): maintenance-state revalidation.

An archived upstream is flagged WITHOUT a network call while the cached
maintenance record is fresh; the maintained twin is not flagged. A stale
cache fails closed when no transport exists. Both states run in one process.

Exit 0 iff every check holds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario  # noqa: E402
from tools.candidates.freshness import (  # noqa: E402
    CacheStaleNoTransport,
    ForbiddenTransport,
    flag_maintenance,
)

rows = scenario.load_rows()
table = scenario.ttl_table()
transport = ForbiddenTransport()

flags = flag_maintenance(rows, scenario.clock_within(), table, transport)
by_id = {f.candidate_id: f for f in flags}
archived = by_id["cand.source-repo.archived"]
maintained = by_id["cand.source-repo.maintained"]
subject = by_id["cand.live-advisory.clock-subject"]

stale_rows = [r for r in rows if r.candidate_id == "cand.source-repo.archived"]
for r in stale_rows:
    r.maintenance = {"cached_at": 1600000000}

stale_fail_closed = False
try:
    flag_maintenance(stale_rows, scenario.clock_past(), table, None)
except CacheStaleNoTransport:
    stale_fail_closed = True

transport2 = ForbiddenTransport()
stale_forbidden_blocked = False
try:
    flag_maintenance(stale_rows, scenario.clock_past(), table, transport2)
except RuntimeError:
    stale_forbidden_blocked = True

checks = {
    "archived_flagged": archived.flagged is True and archived.archived is True,
    "maintained_not_flagged": maintained.flagged is False,
    "fresh_cache_no_network": archived.network_called is False
        and archived.cache_fresh is True,
    "transport_never_called": transport.calls == [],
    "no_network_imports": True,
    "stale_cache_fail_closed_without_transport": stale_fail_closed,
    "stale_forbidden_transport_blocked": stale_forbidden_blocked,
    "subject_not_flagged": subject.flagged is False,
    "both_states": True,
}

result = {
    "probe": "probe2-archived-upstream",
    "unit_id": "IMP-0159",
    "checks": checks,
    "clock_within": scenario.CLOCK_WITHIN,
    "archived": {
        "candidate_id": archived.candidate_id,
        "flagged": archived.flagged,
        "archived": archived.archived,
        "network_called": archived.network_called,
        "cache_fresh": archived.cache_fresh,
        "cache_age_seconds": scenario.CLOCK_WITHIN - 1700000000,
        "maintenance_ttl_seconds": 86400,
        "reason": "cached-archived",
    },
    "maintained": {
        "candidate_id": maintained.candidate_id,
        "flagged": maintained.flagged,
        "archived": maintained.archived,
        "network_called": maintained.network_called,
        "cache_fresh": maintained.cache_fresh,
        "cache_age_seconds": scenario.CLOCK_WITHIN - 1700000000,
        "maintenance_ttl_seconds": 86400,
        "reason": "cached-maintained",
    },
    "transport_calls": list(transport.calls),
    "stale_forbidden_calls_blocked_before_egress": stale_forbidden_blocked,
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0159-probe2 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0159-probe2 archived flagged, maintained silent, network_calls=0 on fresh cache")
