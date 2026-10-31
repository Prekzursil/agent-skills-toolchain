"""Catalog tests for IMP-0098 vulnerability status ingestion (HERMETIC - no network).

- test_known_vulnerable_component_is_flagged: the control fires (lodash 4.17.20 ->
  CVE-2021-23337) through the FakeSource seam.
- DETECTOR CONTROL: a clean component returns CLEAN only in a run where the
  known-vulnerable control also fired; a control-less run downgrades to UNKNOWN.
- test_unreachable_source_yields_unknown_never_clean: an unreachable source and a
  missing tool (osv exit 127) are UNKNOWN - distinct from exit 1 findings.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MKT = Path(__file__).resolve().parents[1]
if str(_MKT) not in sys.path:
    sys.path.insert(0, str(_MKT))

from vuln_ingestion import (  # noqa: E402
    FakeSource,
    KNOWN_CONTROL_CVE,
    Status,
    ids_contain,
    ingest_components,
    interpret_osv_scanner_exit,
)

VULN = {"ecosystem": "npm", "name": "lodash", "version": "4.17.20",
        "purl": "pkg:npm/lodash@4.17.20"}
CLEAN = {"ecosystem": "npm", "name": "clean-pkg", "version": "1.0.0",
         "purl": "pkg:npm/clean-pkg@1.0.0"}
ANSWERS = {
    ("npm", "lodash", "4.17.20"): ["GHSA-35jh-r3h4-6jhm", "CVE-2021-23337"],
    ("npm", "clean-pkg", "1.0.0"): [],
}


def test_known_vulnerable_component_is_flagged() -> None:
    r = ingest_components([VULN], source=FakeSource(answers=ANSWERS))
    row = r["verdicts"][0]
    assert row["status"] == Status.VULNERABLE.value
    assert ids_contain(row["advisory_ids"], KNOWN_CONTROL_CVE)
    assert r["control_fired"] is True
    assert row["queried_at"] and row["advisory_db_snapshot_id"] and row["input_hash"]


def test_clean_only_when_known_vulnerable_control_fired() -> None:
    both = ingest_components([VULN, CLEAN], source=FakeSource(answers=ANSWERS))
    clean_row = next(v for v in both["verdicts"] if v["name"] == "clean-pkg")
    assert both["control_fired"] is True and clean_row["status"] == Status.CLEAN.value

    broken = ingest_components([CLEAN], source=FakeSource(answers=ANSWERS))
    assert broken["control_fired"] is False
    row = broken["verdicts"][0]
    assert row["status"] == Status.UNKNOWN.value, "clean without control must not pass"
    assert "not trusted" in row["warning"]


def test_unreachable_source_yields_unknown_never_clean() -> None:
    r = ingest_components([VULN, CLEAN], source=FakeSource(answers=ANSWERS, unreachable=True))
    assert all(v["status"] == Status.UNKNOWN.value for v in r["verdicts"])
    assert r["vulnerable_count"] == 0 and r["clean_count"] == 0
    # exit-code discipline: 127 is a missing tool (UNKNOWN), not exit 1 (findings)
    assert interpret_osv_scanner_exit(0) == "CLEAN"
    assert interpret_osv_scanner_exit(1) == "VULNERABLE"
    assert interpret_osv_scanner_exit(127) == "UNKNOWN"
    assert interpret_osv_scanner_exit(127) != interpret_osv_scanner_exit(1)
    assert interpret_osv_scanner_exit(3) == "UNKNOWN"


def run_all() -> None:
    test_known_vulnerable_component_is_flagged()
    test_clean_only_when_known_vulnerable_control_fired()
    test_unreachable_source_yields_unknown_never_clean()


if __name__ == "__main__":
    run_all()
    print("SUCCESS:test_vuln_ingestion")
