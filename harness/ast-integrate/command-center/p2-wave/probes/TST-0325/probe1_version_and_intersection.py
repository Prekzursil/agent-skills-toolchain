#!/usr/bin/env python3
"""Probe 1: every aggregate is version-stamped; empty intersection is a refusal.

Catalog tests:
  - Case-set version stamped on every aggregate.
  - Cross-version comparison refuses to run without an intersection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.case_set import (  # noqa: E402
    EmptyIntersectionError,
    UnversionedAggregateError,
    aggregate,
    compare_cross_version,
    compare_or_refuse,
    load_case_set,
    load_ledger,
    outcomes_for,
    require_versioned,
    results_for_run,
    version_case_set,
)

UID = "TST-0325"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0325.json"
CASES = REPO / "command-center" / "bench" / "cases"
LEDGER = REPO / "command-center" / "bench" / "results" / "TST-0325.jsonl"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if f"SUCCESS:{UID}" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if doc.get("unit_id") != UID and doc.get("id") != UID:
        return fail(f"unit_id={doc.get('unit_id')}")

    v1 = load_case_set(CASES / "cs-v1.json")
    v2 = load_case_set(CASES / "cs-v2.json")
    da = load_case_set(CASES / "cs-disjoint-a.json")
    db = load_case_set(CASES / "cs-disjoint-b.json")
    rows = load_ledger(LEDGER)
    res1 = results_for_run(rows, "TST-0325-run-cs-v1")
    res2 = results_for_run(rows, "TST-0325-run-cs-v2")

    agg1 = aggregate(res1, v1["cases"], run_id="TST-0325-run-cs-v1", label="cs-v1")
    agg2 = aggregate(res2, v2["cases"], run_id="TST-0325-run-cs-v2", label="cs-v2")
    for name, agg, cases in (
        ("v1", agg1, v1["cases"]),
        ("v2", agg2, v2["cases"]),
    ):
        try:
            require_versioned(agg)
        except UnversionedAggregateError as exc:
            return fail(f"{name} unversioned: {exc}")
        live = version_case_set(cases)["id"]
        if agg["case_set_version"] != live:
            return fail(f"{name} stamp {agg['case_set_version']} != live {live}")
        if agg["case_set_version"] != agg["case_set_version"]:
            return fail(f"{name} stamp unstable")

    forged = dict(agg1)
    forged.pop("case_set_version", None)
    try:
        require_versioned(forged)
        return fail("stripped stamp was accepted")
    except UnversionedAggregateError:
        pass

    # Empty intersection must raise, not emit a numeric delta.
    raised = False
    try:
        compare_cross_version(
            outcomes_for(da["cases"]),
            da["cases"],
            outcomes_for(db["cases"]),
            db["cases"],
        )
    except EmptyIntersectionError as exc:
        raised = True
        if exc.n_a < 1 or exc.n_b < 1:
            return fail("refusal hid set sizes")
        if not exc.version_a or not exc.version_b:
            return fail("refusal missing versions")
        if exc.version_a == exc.version_b:
            return fail("disjoint sets unexpectedly same version")
    if not raised:
        return fail("disjoint comparison returned instead of refusing")

    refused = compare_or_refuse(
        outcomes_for(da["cases"]),
        da["cases"],
        outcomes_for(db["cases"]),
        db["cases"],
    )
    if refused.get("status") != "REFUSED":
        return fail(f"compare_or_refuse status={refused.get('status')}")
    if refused.get("intersection_n") != 0:
        return fail("refused record claimed a non-empty intersection")
    if refused.get("naive_delta") is not None or refused.get("intersection_delta") is not None:
        return fail("refused record still carried a delta")

    report = doc.get("report") or {}
    rec_aggs = report.get("aggregates") or []
    if len(rec_aggs) < 2:
        return fail("receipt aggregates missing")
    for item in rec_aggs:
        try:
            require_versioned(item)
        except UnversionedAggregateError:
            return fail(f"receipt aggregate unstamped {item.get('case_set_label')}")

    rec_refused = report.get("empty_intersection_refusal") or {}
    if rec_refused.get("status") != "REFUSED":
        return fail("receipt missing REFUSED empty-intersection control")

    out = {
        "probe": "probe1-version-and-intersection",
        "unit_id": UID,
        "pass": True,
        "agg_v1_version": agg1["case_set_version"],
        "agg_v2_version": agg2["case_set_version"],
        "versions_differ": agg1["case_set_version"] != agg2["case_set_version"],
        "stripped_stamp_rejected": True,
        "empty_intersection_raised": True,
        "refused_status": refused["status"],
        "refused_intersection_n": refused["intersection_n"],
        "receipt_aggregates_stamped": len(rec_aggs),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    if not out["versions_differ"]:
        return fail("v1 and v2 share a version after adding 20 cases")
    print(
        "SUCCESS:TST-0325-probe1 version-stamped aggregates; "
        "empty intersection refused"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
