#!/usr/bin/env python3
"""Probe 1: cost fields on every row; missing cost is rejected; vendor reconcile."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from bench.cost import (  # noqa: E402
    REQUIRED_COST_FIELDS,
    MissingCostError,
    SpendMismatchError,
    VendorDiscrepancyReject,
    admit_quota,
    coverage_complete,
    ingest_row,
    parse_cost_record,
    quality_cost_delta,
    reconcile_vendor,
    validate_cost_fields,
)
from fixtures import (  # noqa: E402
    complete_rows,
    forged_spend_row,
    incomplete_rows,
    matching_vendor,
    mismatch_vendor,
    remaining_quota,
)

UNIT = "TST-0304"
ART = REPO / "command-center/receipts/TST-0304.json"
SENTINEL = "SUCCESS:TST-0304"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    rows = complete_rows()
    if len(rows) < 4:
        return fail("candidate set too small")

    accepted = []
    vendor_reports = []
    for row in rows:
        rec, disc = ingest_row(row, matching_vendor(row), strict_vendor=True)
        if not disc.match:
            return fail(f"honest row {rec.candidate_id} vendor mismatch")
        if disc.delta_tokens_in != 0 or disc.delta_tokens_out != 0:
            return fail(f"zero-delta not reported as zero for {rec.candidate_id}")
        accepted.append(rec)
        vendor_reports.append(disc.as_dict())

    cov = coverage_complete(rows)
    if cov["coverage"] != 1.0 or cov["rejected"] != 0:
        return fail(f"complete-set coverage {cov}")
    for rec in accepted:
        as_row = rec.as_dict()
        validate_cost_fields(as_row)

    rejected_labels = []
    for bad in incomplete_rows():
        try:
            validate_cost_fields(bad)
            return fail(f"incomplete row accepted {bad.get('label')}")
        except MissingCostError:
            rejected_labels.append(bad["label"])
    if len(rejected_labels) != len(incomplete_rows()):
        return fail("not every incomplete row was rejected")

    try:
        parse_cost_record(forged_spend_row())
        return fail("forged spend was accepted")
    except SpendMismatchError:
        pass

    mismatch_row = dict(rows[0])
    try:
        ingest_row(mismatch_row, mismatch_vendor(mismatch_row), strict_vendor=True)
        return fail("vendor mismatch was accepted under strict ingest")
    except VendorDiscrepancyReject as exc:
        reported = exc.discrepancy
        if reported.match:
            return fail("mismatch discrepancy claimed match")
        if reported.delta_tokens_in == 0 and reported.delta_tokens_out == 0:
            return fail("mismatch discrepancy hid the delta")
        mismatch_report = reported.as_dict()

    # Non-strict path still *reports* the discrepancy rather than swallowing it.
    rec0 = parse_cost_record(mismatch_row)
    loose = reconcile_vendor(rec0, mismatch_vendor(mismatch_row))
    if loose.match or loose.delta_tokens_in == 0:
        return fail("non-strict reconcile hid the vendor delta")

    by_id = {rec.candidate_id: rec for rec in accepted}
    delta_free = quality_cost_delta(by_id["A"], by_id["B"])
    delta_costly = quality_cost_delta(by_id["A"], by_id["C"])
    if abs(float(delta_free["quality_relative"]) - 0.02) > 1e-12:
        return fail(f"B quality relative {delta_free['quality_relative']}")
    if abs(float(delta_free["tokens_ratio"]) - 1.0) > 1e-12:
        return fail(f"B tokens ratio {delta_free['tokens_ratio']}")
    if abs(float(delta_costly["quality_relative"]) - 0.02) > 1e-12:
        return fail(f"C quality relative {delta_costly['quality_relative']}")
    if abs(float(delta_costly["tokens_ratio"]) - 6.0) > 1e-12:
        return fail(f"C tokens ratio {delta_costly['tokens_ratio']}")
    if delta_free["decision_note"] == delta_costly["decision_note"]:
        return fail("2% free and 2% at 6x tokens collapsed to one note")

    quota = remaining_quota()
    admit_a = admit_quota(by_id["A"], quota)
    admit_c = admit_quota(by_id["C"], quota)
    if not admit_a["admitted"]:
        return fail("quota refused the in-budget baseline")
    if admit_c["admitted"] or "tokens" not in admit_c["breaches"]:
        return fail(f"quota did not refuse 6x-token candidate {admit_c}")

    payload = {
        "pass": True,
        "probe": "probe1-cost-fields",
        "unit_id": UNIT,
        "n_complete": len(accepted),
        "coverage_on_complete": cov["coverage"],
        "required_cost_fields": list(REQUIRED_COST_FIELDS),
        "incomplete_rejected": rejected_labels,
        "vendor_match_all_complete": all(v["match"] for v in vendor_reports),
        "vendor_mismatch": mismatch_report,
        "delta_free": delta_free,
        "delta_costly": delta_costly,
        "quota": {"admit_A": admit_a["admitted"], "admit_C": admit_c["admitted"]},
    }
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            return fail("completion_sentinel absent from artifact")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        measured = doc.get("measured") or {}
        if measured.get("complete_coverage") != 1.0:
            return fail("receipt complete_coverage drift")
        if measured.get("incomplete_rejected") != len(rejected_labels):
            return fail("receipt incomplete_rejected drift")

    print(
        f"complete={len(accepted)} coverage=1.0 incomplete_rejected={len(rejected_labels)} "
        f"vendor_mismatch_d_in={mismatch_report['delta_tokens_in']} "
        f"quota_A={admit_a['admitted']} quota_C={admit_c['admitted']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 cost fields complete; missing rejected; vendor delta reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
