#!/usr/bin/env python3
"""Probe 2: two tools, recall-before-unbuilt, NOT-CHECKED downgrade, mutant control."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import engine as E  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0066-negative-result-recheck.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0066-probe2 {msg}")
    return 1


def main() -> int:
    live = E.retest_all()
    by_id = {r["id"]: r for r in live["records"]}

    for rec in live["records"]:
        if rec["classification"] == "NOT-CHECKED":
            continue
        if rec.get("fingerprints_differ") is not True:
            return fail(f"{rec['id']} tools share a fingerprint")
        a = rec["tool_a"]
        b = rec["tool_b"]
        if (a.get("tool"), a.get("field"), a.get("measurement_kind")) == (
            b.get("tool"),
            b.get("field"),
            b.get("measurement_kind"),
        ):
            return fail(f"{rec['id']} tools are not mechanically different")

    unchecked = by_id.get("P-NO-CONTROL")
    if not unchecked or unchecked["classification"] != "NOT-CHECKED":
        return fail("no-control claim was not downgraded to NOT-CHECKED")
    if unchecked.get("control_found_known_present"):
        return fail("NOT-CHECKED row claims a control hit")

    if live["recall"].get("ran") is not True:
        return fail("recall was not run")
    if live["recall"].get("filesystem_control_hits", 0) < 1:
        return fail("recall filesystem control missed known-present note")
    unbuilt = [
        r
        for r in live["records"]
        if r["classification"] in {"CONFIRMED_ABSENCE", "RECALL_NOT_DETECTION"}
        and "unbuilt" in r["claim"].lower()
        or r["id"] in {"L-BASIC-MEMORY-PROGRAM-B", "P-RECALL-NOT-DETECTION"}
    ]
    for rec in unbuilt:
        if rec.get("recall_ran") is not True:
            return fail(f"{rec['id']} unbuilt without recall")

    recall_row = by_id.get("P-RECALL-NOT-DETECTION")
    if not recall_row or recall_row["classification"] != "RECALL_NOT_DETECTION":
        return fail("planted recall-not-detection did not fire")
    if (recall_row["tool_a"]["hit_count"] > 0) or (recall_row["tool_b"]["hit_count"] < 1):
        return fail("recall row is not index-miss / filesystem-hit")

    for rid in ("P-WRONG-PATH", "P-WRONG-FIELD", "P-WRONG-SHELL-PATH"):
        row = by_id.get(rid)
        if not row or row["classification"] != "DETECTOR_FAILURE":
            return fail(f"{rid} was not detector-failure")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    view = C.domain_view(doc)
    if view.get("reviewer", {}).get("independent") is not True:
        return fail("reviewer is not independent")
    if view.get("reviewer", {}).get("re_ran_detector_control") is not True:
        return fail("reviewer did not re-run detector control")

    schema_errs = SC.iter_errors(doc)
    if schema_errs:
        print(schema_errs[0])
        return fail("artifact schema-invalid")

    mutant = copy.deepcopy(doc)
    report = mutant.get("report") if isinstance(mutant.get("report"), dict) else mutant
    absences = report.get("absences") or mutant.get("absences") or []
    if not absences:
        return fail("artifact has no absences to mutant")
    absences[0]["control_found_known_present"] = False
    mutant_errs = SC.iter_errors(mutant)
    if not mutant_errs:
        mutant_contract = C.check_document(mutant)
        if not mutant_contract:
            return fail("mutant absence without control was accepted")
    print(f"mutant_rejected=True schema_errs={len(mutant_errs)}")

    live_df = live["summary"]["detector_failure"]
    art_df = (view.get("summary") or {}).get("detector_failure")
    if live_df != art_df:
        return fail(f"detector_failure drift live={live_df} art={art_df}")

    payload = {
        "detector_failure": live_df,
        "not_checked": 1,
        "pass": True,
        "probe": "probe2-independence",
        "recall_ran": True,
        "unit_id": "CNF-0066",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNF-0066-probe2 two-tools recall NOT-CHECKED mutant-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
