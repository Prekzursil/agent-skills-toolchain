#!/usr/bin/env python3
"""Probe 2: independent second source (GitHub Advisory API) plus fail-closed paths.

Signal 2 of IMP-0098: the same lodash@4.17.20 query through GitHub advisories must
contain CVE-2021-23337, and the intersection with OSV must contain it. An
unreachable source yields UNKNOWN, never CLEAN. osv exit 127 is not exit 1.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.vuln_ingestion import (  # noqa: E402
    CLEAN_CONTROL_NAME,
    KNOWN_CONTROL_CVE,
    FakeSource,
    GithubAdvisorySource,
    OsvHttpSource,
    SbomStore,
    ids_contain,
    ingest_components,
    interpret_osv_scanner_exit,
    known_control_component,
    two_source_known_cve,
)

RECEIPT = REPO / "command-center/receipts/IMP-0098.json"
DEAD_OSV = "http://127.0.0.1:1/v1/query"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0098-probe2 {msg}")
    return 1


def main() -> int:
    if interpret_osv_scanner_exit(127, tool_found=False) == interpret_osv_scanner_exit(1, tool_found=True):
        return fail("osv exit 127 collapsed into exit 1")
    if interpret_osv_scanner_exit(127, tool_found=False) != "UNKNOWN":
        return fail("osv exit 127 is not UNKNOWN")
    if interpret_osv_scanner_exit(1, tool_found=True) != "VULNERABLE":
        return fail("osv exit 1 is not VULNERABLE")

    control = known_control_component()
    confirm = two_source_known_cve(control, OsvHttpSource(max_attempts=3), GithubAdvisorySource(max_attempts=3))
    if not confirm["known_cve_in_both"]:
        return fail(
            f"{KNOWN_CONTROL_CVE} not in both sources; "
            f"osv={confirm['primary']['advisory_ids'][:12]} "
            f"github={confirm['secondary']['advisory_ids'][:12]} "
            f"intersection={confirm['intersection'][:12]}"
        )
    if not ids_contain(confirm["primary"]["advisory_ids"], KNOWN_CONTROL_CVE):
        return fail("OSV missing known CVE")
    if not ids_contain(confirm["secondary"]["advisory_ids"], KNOWN_CONTROL_CVE):
        return fail("GitHub advisories missing known CVE")
    if not confirm["primary"]["snapshot_id"] or not confirm["secondary"]["snapshot_id"]:
        return fail("a source omitted advisory_db_snapshot_id")

    store = SbomStore(HERE / "fixtures" / "sboms")
    dead = ingest_components(
        store.all_components(),
        OsvHttpSource(query_url=DEAD_OSV, timeout=2.0, max_attempts=1),
    )
    if dead["clean_count"] != 0:
        return fail("unreachable source emitted CLEAN")
    if any(v["status"] != "UNKNOWN" for v in dead["verdicts"]):
        return fail(f"unreachable source produced non-UNKNOWN: {dead['verdicts']}")
    if any(v["name"] == CLEAN_CONTROL_NAME and v["status"] == "CLEAN" for v in dead["verdicts"]):
        return fail("fetch failure rendered CLEAN")

    silent = FakeSource(
        {
            ("npm", "lodash", "4.17.20"): [],
            ("npm", CLEAN_CONTROL_NAME, "1.0.0"): [],
        }
    )
    gated = ingest_components(store.all_components(), silent)
    if any(v["status"] == "CLEAN" for v in gated["verdicts"]):
        return fail("CLEAN emitted while known-vulnerable control was silent")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {doc.get('state')}")
        two = doc.get("two_source_confirmation") or {}
        if two and not two.get("known_cve_in_both"):
            return fail("receipt two_source_confirmation.known_cve_in_both is not true")
        if KNOWN_CONTROL_CVE not in text:
            return fail("receipt does not name the known CVE")

    summary = {
        "probe": "probe2-independent-github",
        "unit_id": "IMP-0098",
        "known_cve_in_both": confirm["known_cve_in_both"],
        "intersection": confirm["intersection"],
        "osv_snapshot_id": confirm["primary"]["snapshot_id"],
        "github_snapshot_id": confirm["secondary"]["snapshot_id"],
        "unreachable_never_clean": True,
        "exit_127_distinct_from_1": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"known_cve_in_both={confirm['known_cve_in_both']} "
        f"intersection_n={len(confirm['intersection'])} unreachable_clean=0"
    )
    print("SUCCESS:IMP-0098-probe2 two-source CVE and fail-closed UNKNOWN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
