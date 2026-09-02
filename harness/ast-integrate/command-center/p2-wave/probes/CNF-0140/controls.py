"""Named detector controls required by CNF-0140."""
from __future__ import annotations

from typing import Any

from census import census, coverage_is_full_gaps, cross_registry_ok, refuses_vacuous_full_coverage
from scenario import RECORDS, materialize


def known_present() -> dict[str, Any]:
    roots = materialize()
    root = roots["known_present"]
    result = census(root / "CLAIM-REGISTRY.json", root / "records")
    by_id = {row["claim_id"]: row for row in result["ledger"]}
    present_ok = (
        "CLAIM-P0-PRESENT" in by_id
        and by_id["CLAIM-P0-PRESENT"]["status"] == "RESOLVED"
        and by_id["CLAIM-P0-PRESENT"]["record_id"] == RECORDS["CLAIM-P0-PRESENT"]
    )
    deleted_ok = (
        "CLAIM-P0-DELETED" in by_id
        and by_id["CLAIM-P0-DELETED"]["status"] == "GAP"
        and by_id["CLAIM-P0-DELETED"]["record_id"] == "NOT-CHECKED"
    )
    p2_excluded = "CLAIM-P2-LOW" not in by_id and "CLAIM-P2-UNDER" not in by_id
    ungraded_named = "CLAIM-UNGRADED" in result["ungraded_claim_ids"]
    n = int(result["counts"]["registry_p0_p1_count"])
    counts_ok = n == 5 and int(result["counts"]["ledger_row_count"]) == 5
    xref, xref_why = cross_registry_ok(result)
    return {
        "ok": present_ok and deleted_ok and p2_excluded and ungraded_named and counts_ok and xref,
        "present_ok": present_ok,
        "deleted_ok": deleted_ok,
        "p2_excluded": p2_excluded,
        "ungraded_named": ungraded_named,
        "counts_ok": counts_ok,
        "cross_registry_ok": xref,
        "cross_registry_why": xref_why,
        "resolved_count": result["counts"]["resolved_count"],
        "gap_count": result["counts"]["gap_count"],
        "ledger_ids": [r["claim_id"] for r in result["ledger"]],
        "result": result,
    }


def empty_records_detector() -> dict[str, Any]:
    roots = materialize()
    root = roots["empty_records"]
    result = census(root / "CLAIM-REGISTRY.json", root / "records")
    full_gaps = coverage_is_full_gaps(result)
    not_full_coverage = result["counts"]["coverage_rate"] != 1.0
    return {
        "ok": full_gaps and not_full_coverage and int(result["counts"]["registry_p0_p1_count"]) == 5,
        "full_gaps": full_gaps,
        "not_full_coverage": not_full_coverage,
        "coverage_rate": result["counts"]["coverage_rate"],
        "gap_rate": result["counts"]["gap_rate"],
        "n": result["counts"]["registry_p0_p1_count"],
        "listing_count": result["counts"]["records_directory_listing_count"],
        "result": result,
    }


def empty_population_detector() -> dict[str, Any]:
    roots = materialize()
    root = roots["empty_population"]
    result = census(root / "CLAIM-REGISTRY.json", root / "records")
    ok = refuses_vacuous_full_coverage(result)
    return {
        "ok": ok,
        "coverage_rate": result["counts"]["coverage_rate"],
        "n": result["counts"]["registry_p0_p1_count"],
        "result": result,
    }


def severity_coupling() -> dict[str, Any]:
    roots = materialize()
    root = roots["regrade"]
    before = census(root / "CLAIM-REGISTRY.json", root / "records")
    after = census(
        root / "CLAIM-REGISTRY.json",
        root / "records",
        root / "CNF-0142.json",
    )
    before_ids = {r["claim_id"] for r in before["ledger"]}
    after_ids = {r["claim_id"] for r in after["ledger"]}
    appeared = "CLAIM-P2-UNDER" in after_ids and "CLAIM-P2-UNDER" not in before_ids
    row = next((r for r in after["ledger"] if r["claim_id"] == "CLAIM-P2-UNDER"), None)
    regraded = bool(row and row.get("regraded") and row.get("effective_severity") == "P1")
    still_missing_record = bool(row and row.get("status") == "GAP")
    return {
        "ok": appeared and regraded and still_missing_record,
        "appeared": appeared,
        "regraded": regraded,
        "still_missing_record": still_missing_record,
        "before_n": before["counts"]["registry_p0_p1_count"],
        "after_n": after["counts"]["registry_p0_p1_count"],
        "after_ids": sorted(after_ids),
    }


def cross_registry() -> dict[str, Any]:
    kp = known_present()
    return {
        "ok": bool(kp["cross_registry_ok"]),
        "why": kp["cross_registry_why"],
        "cited": kp["result"]["counts"]["cited_record_count"],
        "parseable": kp["result"]["counts"]["cited_records_exist_and_parse"],
        "unparseable_files": kp["result"]["records_unparseable"],
    }


def spotcheck_five() -> dict[str, Any]:
    """Reviewer: five census rows against raw record files."""
    kp = known_present()
    result = kp["result"]
    roots = materialize()
    rec_dir = roots["known_present"] / "records"
    checks = []
    resolved_rows = [r for r in result["ledger"] if r["status"] == "RESOLVED"]
    gap_rows = [r for r in result["ledger"] if r["status"] == "GAP"]
    sample = resolved_rows[:4] + gap_rows[:1]
    for row in sample:
        if row["record_id"] == "NOT-CHECKED":
            leftover = rec_dir / "B09-REC-CLAIM-P0-DELETED.json"
            checks.append(
                {
                    "claim_id": row["claim_id"],
                    "expected": "GAP",
                    "ok": not leftover.is_file() and row["status"] == "GAP",
                }
            )
            continue
        path = rec_dir / f"{row['record_id']}.json"
        exists = path.is_file()
        parsed_claim = None
        if exists:
            import json

            doc = json.loads(path.read_text(encoding="utf-8"))
            parsed_claim = doc.get("claim_id")
        checks.append(
            {
                "claim_id": row["claim_id"],
                "record_id": row["record_id"],
                "ok": exists and parsed_claim == row["claim_id"],
            }
        )
    resolved_ok = sum(1 for c in checks if c.get("record_id")) >= 4
    ok = len(checks) == 5 and all(c["ok"] for c in checks) and resolved_ok
    return {"ok": ok, "checks": checks}


def all_controls() -> dict[str, Any]:
    parts = {
        "known_present": known_present(),
        "empty_records": empty_records_detector(),
        "empty_population": empty_population_detector(),
        "severity_coupling": severity_coupling(),
        "cross_registry": cross_registry(),
        "spotcheck_five": spotcheck_five(),
    }
    ok = all(bool(v.get("ok")) for v in parts.values())
    return {"ok": ok, "parts": parts}
