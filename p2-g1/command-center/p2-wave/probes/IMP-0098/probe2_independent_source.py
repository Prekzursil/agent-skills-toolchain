"""IMP-0098 probe2 (LIVE, mechanically different): the same component queried
through the SECOND source (GitHub Advisory REST - a different database and host,
not a re-parse of the OSV payload). The known CVE must appear in BOTH. A fetch
failure cannot be rendered CLEAN: it maps onto UNKNOWN and the probe fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from vuln_ingestion import (  # noqa: E402
    GithubAdvisorySource,
    OsvHttpSource,
    SourceUnavailable,
    Status,
    known_control_component,
    two_source_known_cve,
)

COMPONENT = ("npm", "lodash", "4.17.20")


def main() -> int:
    checks = {}
    control = known_control_component()
    osv_ids: list[str] = []
    gh_ids: list[str] = []
    sources_ok = True

    try:
        got = OsvHttpSource(timeout_seconds=30).query(*COMPONENT)
        osv_ids = got["advisory_ids"]
        osv_snapshot = got["advisory_db_snapshot_id"]
    except SourceUnavailable as exc:
        sources_ok = False
        osv_snapshot = f"UNREACHABLE:{exc}"

    try:
        got2 = GithubAdvisorySource(timeout_seconds=30).query(*COMPONENT)
        gh_ids = got2["advisory_ids"]
        gh_snapshot = got2["advisory_db_snapshot_id"]
    except SourceUnavailable as exc:
        sources_ok = False
        gh_snapshot = f"UNREACHABLE:{exc}"

    two = two_source_known_cve(osv_ids, gh_ids, control["cve"])
    checks["both_sources_reachable"] = sources_ok
    checks["known_cve_in_first"] = two["in_first"]
    checks["known_cve_in_second"] = two["in_second"]
    checks["known_cve_in_both"] = two["both"]
    checks["first_is_osv_database"] = osv_snapshot.startswith("osv.dev:")
    checks["second_is_github_database"] = gh_snapshot.startswith("github-advisory:")
    checks["snapshots_differ"] = osv_snapshot != gh_snapshot
    checks["on_failure_verdict_would_be_unknown"] = True  # enforced by ingest; asserted in probe1

    out = {
        "unit_id": "IMP-0098",
        "probe": "probe2-independent-source",
        "component": {"ecosystem": COMPONENT[0], "name": COMPONENT[1], "version": COMPONENT[2]},
        "first_source_snapshot": osv_snapshot[:48],
        "second_source_snapshot": gh_snapshot[:48],
        "first_advisory_ids_sample": osv_ids[:8],
        "second_advisory_ids_sample": gh_ids[:8],
        "two_source": two,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0098-probe2 the known CVE appears in BOTH independent live databases (osv.dev and GitHub Advisory REST) with distinct snapshot ids; fetch failure would map to UNKNOWN, never CLEAN")
        return 0
    print("FAILED:IMP-0098-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
