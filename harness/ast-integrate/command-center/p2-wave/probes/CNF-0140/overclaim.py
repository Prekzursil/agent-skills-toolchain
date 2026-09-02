"""Refuse a CONFIRMED census that launders gaps, emptiness, or a percentage-only report."""
from __future__ import annotations

from typing import Any


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "doc-not-object"
    verdict = str(doc.get("verdict") or "")
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{state}"
    census = doc.get("census")
    counts = doc.get("counts")
    if not isinstance(census, dict):
        return False, "census-missing"
    if not isinstance(counts, dict):
        return False, "counts-missing"
    ledger = census.get("ledger")
    if not isinstance(ledger, list):
        return False, "ledger-missing"
    for i, row in enumerate(ledger):
        if not isinstance(row, dict):
            return False, f"ledger[{i}]-not-object"
        if not str(row.get("claim_id") or "").strip():
            return False, f"ledger[{i}]-no-claim-id"
        rid = str(row.get("record_id") or "").strip()
        if not rid:
            return False, f"ledger[{i}]-no-record-id"
        if rid != "NOT-CHECKED" and str(row.get("status") or "") != "RESOLVED":
            return False, f"ledger[{i}]-id-without-resolved"
        if rid == "NOT-CHECKED" and str(row.get("status") or "") != "GAP":
            return False, f"ledger[{i}]-NOT-CHECKED-not-gap"
    try:
        n = int(counts["registry_p0_p1_count"])
        listing = int(counts["records_directory_listing_count"])
        ledger_n = int(counts["ledger_row_count"])
        gaps = int(counts["gap_count"])
    except (KeyError, TypeError, ValueError):
        return False, "required-counts-missing"
    if ledger_n != len(ledger) or n != ledger_n:
        return False, "ledger-count-drift"
    if n > 0 and not ledger:
        return False, "percentage-without-id-list"
    if "coverage_rate" in counts and n > 0 and not ledger:
        return False, "coverage-without-ledger"
    if n == 0:
        if counts.get("coverage_rate") is not None:
            return False, "empty-population-claimed-coverage"
        if verdict == "CONFIRMED":
            return False, "CONFIRMED-on-empty-population"
    if verdict == "CONFIRMED":
        if census.get("registry_present") is not True:
            return False, "CONFIRMED-registry-absent"
        if gaps != 0:
            return False, "CONFIRMED-with-gaps"
        if any(r.get("record_id") == "NOT-CHECKED" for r in ledger):
            return False, "CONFIRMED-with-NOT-CHECKED"
        if listing < 1:
            return False, "CONFIRMED-with-empty-records-dir"
    # Second signal must be published even when it disagrees with registry n.
    if "records_directory_listing_count" not in counts:
        return False, "listing-count-absent"
    return True, f"verdict={verdict} n={n} listing={listing} gaps={gaps}"
