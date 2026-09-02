#!/usr/bin/env python3
"""Probe 1: ingest stored SBOMs via OSV; known historical CVE must be present.

Signal 1 of IMP-0098: the ingested advisory set for lodash@4.17.20 contains
CVE-2021-23337. CLEAN on the innocent component is accepted only because that
known-vulnerable control fired in the same run. Offline unit tests also run.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.vuln_ingestion import (  # noqa: E402
    CLEAN_CONTROL_NAME,
    KNOWN_CONTROL_CVE,
    KNOWN_CONTROL_NAME,
    KNOWN_CONTROL_VERSION,
    OsvHttpSource,
    SbomStore,
    ids_contain,
    ingest_components,
)
from marketplace.tests.test_vuln_ingestion import VulnIngestionTests  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0098.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0098-probe1 {msg}")
    return 1


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VulnIngestionTests)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    if not result.wasSuccessful():
        return fail(f"unittest failures={len(result.failures)} errors={len(result.errors)}")

    store = SbomStore(HERE / "fixtures" / "sboms")
    comps = store.all_components()
    if len(comps) < 2:
        return fail(f"stored SBOM component count {len(comps)} < 2")

    report = ingest_components(comps, OsvHttpSource(max_attempts=3))
    if not report["control_fired"]:
        return fail("known-vulnerable control did not fire against live OSV")

    lodash = [
        v
        for v in report["verdicts"]
        if v["name"] == KNOWN_CONTROL_NAME and v["version"] == KNOWN_CONTROL_VERSION
    ]
    if not lodash:
        return fail("lodash@4.17.20 missing from ingested verdicts")
    if any(v["status"] != "VULNERABLE" for v in lodash):
        return fail(f"lodash not VULNERABLE: {lodash}")
    if any(not ids_contain(v["advisory_ids"], KNOWN_CONTROL_CVE) for v in lodash):
        return fail(f"{KNOWN_CONTROL_CVE} absent from lodash advisory set: {lodash[0]['advisory_ids']}")
    if any(not v["queried_at"] or not v["advisory_db_snapshot_id"] for v in lodash):
        return fail("lodash verdict missing timestamp or snapshot id")

    innocent = [v for v in report["verdicts"] if v["name"] == CLEAN_CONTROL_NAME]
    if not innocent:
        return fail("innocent component missing from ingested verdicts")
    if any(v["status"] != "CLEAN" for v in innocent):
        return fail(f"innocent not CLEAN (control fired={report['control_fired']}): {innocent}")
    if not report["control_fired"]:
        return fail("CLEAN accepted without control — detector-failure")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {doc.get('state')}")
        if "SUCCESS:IMP-0098" not in text:
            return fail("receipt sentinel absent")
        if KNOWN_CONTROL_CVE not in text:
            return fail("receipt does not name the known CVE")

    summary = {
        "probe": "probe1-osv-ingest",
        "unit_id": "IMP-0098",
        "control_fired": report["control_fired"],
        "known_cve": KNOWN_CONTROL_CVE,
        "lodash_status": lodash[0]["status"],
        "lodash_ids": lodash[0]["advisory_ids"],
        "snapshot_id": lodash[0]["advisory_db_snapshot_id"],
        "queried_at": report["queried_at"],
        "innocent_status": innocent[0]["status"],
        "unittest_pass": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"control_fired={report['control_fired']} lodash={lodash[0]['status']} "
        f"innocent={innocent[0]['status']} cve={KNOWN_CONTROL_CVE}"
    )
    print("SUCCESS:IMP-0098-probe1 known-CVE ingest and detector-gated CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
