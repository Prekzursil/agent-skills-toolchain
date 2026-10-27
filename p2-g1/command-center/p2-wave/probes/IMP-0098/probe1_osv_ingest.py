"""IMP-0098 probe1 (LIVE): ingest the SBOM components through the real OSV API.

Signals: the KNOWN historical CVE (CVE-2021-23337 in lodash 4.17.20) is ingested
VULNERABLE with a time-stamped snapshot; the clean control is CLEAN only because
the known-vulnerable control fired in the SAME run; an unreachable source yields
UNKNOWN, never CLEAN (hermetic seam); osv exit 127 is UNKNOWN, not exit 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from vuln_ingestion import (  # noqa: E402
    FakeSource,
    SbomStore,
    Status,
    ids_contain,
    ingest_components,
    interpret_osv_scanner_exit,
    known_control_component,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "sboms"


def main() -> int:
    checks = {}
    store = SbomStore.from_paths(FIX / "demo-vuln@1.0.0.cdx.json",
                                 FIX / "demo-clean@1.0.0.cdx.json")
    comps = store.components()
    checks["sbom_components_two"] = len(comps) == 2

    report = ingest_components(comps, source=__import__("vuln_ingestion").OsvHttpSource(timeout_seconds=30))
    rows = {v["name"]: v for v in report["verdicts"]}
    vuln_row = rows.get("lodash")
    clean_row = rows.get("@ast-integrate/no-such-package-imp-0098")

    control = known_control_component()
    checks["known_control_used"] = control["cve"] == "CVE-2021-23337"
    checks["known_vulnerable_flagged_live"] = bool(
        vuln_row and vuln_row["status"] == Status.VULNERABLE.value
        and ids_contain(vuln_row["advisory_ids"], control["cve"])
    )
    checks["control_fired_this_run"] = report["control_fired"] is True
    checks["verdict_time_stamped"] = bool(
        vuln_row and vuln_row["queried_at"]
        and str(vuln_row["advisory_db_snapshot_id"]).startswith("osv.dev:")
        and vuln_row["input_hash"]
    )
    checks["clean_gated_on_control"] = bool(
        clean_row and clean_row["status"] == Status.CLEAN.value
        and report["control_fired"]
    )

    # detector control in the SAME run: with the control absent, clean is UNKNOWN
    broken = ingest_components([comps[1]], source=__import__("vuln_ingestion").FakeSource(answers={}))
    checks["clean_not_trusted_without_control"] = (
        broken["verdicts"][0]["status"] == Status.UNKNOWN.value
    )

    # unreachable source: UNKNOWN, never CLEAN (hermetic seam, no network)
    down = ingest_components(comps, source=FakeSource(unreachable=True))
    checks["unreachable_yields_unknown"] = all(
        v["status"] == Status.UNKNOWN.value for v in down["verdicts"]
    )
    checks["never_clean_on_failure"] = down["never_clean_on_failure"]
    checks["exit_127_unknown_not_findings"] = (
        interpret_osv_scanner_exit(127) == "UNKNOWN"
        and interpret_osv_scanner_exit(127) != interpret_osv_scanner_exit(1)
        and interpret_osv_scanner_exit(1) == "VULNERABLE"
    )

    slim = {k: report[k] for k in ("control_fired", "component_count",
                                   "vulnerable_count", "clean_count", "unknown_count",
                                   "never_clean_on_failure", "queried_at")}
    out = {
        "unit_id": "IMP-0098",
        "probe": "probe1-osv-ingest",
        "live_source": "api.osv.dev/v1/query",
        "known_control": control,
        "report": slim,
        "vuln_verdict": {k: vuln_row[k] for k in ("name", "version", "status",
                                                  "advisory_ids", "advisory_db_snapshot_id",
                                                  "queried_at", "input_hash")} if vuln_row else None,
        "clean_verdict": {k: clean_row[k] for k in ("name", "status", "warning")} if clean_row else None,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0098-probe1 live OSV ingest flags the known CVE with a time-stamped snapshot; clean verdict gated on the control firing in-run; unreachable maps to UNKNOWN, exit 127 is not exit 1")
        return 0
    print("FAILED:IMP-0098-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
