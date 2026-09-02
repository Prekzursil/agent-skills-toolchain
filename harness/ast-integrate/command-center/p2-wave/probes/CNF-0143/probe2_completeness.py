#!/usr/bin/env python3
"""Probe 2: completeness (schema) + UNKNOWNS-REGISTER cross-check.

Mechanically different from probe 1: does not recompute rates. Validates that a
BLOCKED record with an empty prerequisite is unrepresentable, that every
accounted BLOCKED prerequisite appears in UNKNOWNS-REGISTER.md, and that a
planted-absent prerequisite is detected. Independent reviewer hand-counts one
stratum.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import accounting as A  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0143.json"
SCHEMA = REPO / "command-center/schema/program-gate-report.schema.json"
OVERLAY = HERE / "program-gate-report.overlay.schema.json"
UNK = REPO / "command-center/UNKNOWNS-REGISTER.md"
PLANTED = "missing-prerequisite:PLANTED-ABSENT-CNF-0143"


def main() -> int:
    bundle = A.load_control_set()
    good = bundle["records_nonempty_blocked"]
    bad = bundle["records_bad_prerequisite"][0]
    frame = bundle["frame"]

    good_blocked = [r for r in good if r["verdict"] == "BLOCKED"]
    if len(good_blocked) < 1:
        print("FAILED:CNF-0143-probe2 no good BLOCKED records")
        return 1
    for rec in good_blocked:
        errs = A.validate_record_schema(rec)
        print(f"good_blocked {rec['claim_id']} schema_errs={errs}")
        if errs:
            print("FAILED:CNF-0143-probe2 well-formed BLOCKED rejected")
            return 1

    bad_errs = A.validate_record_schema(bad)
    print(f"bad_empty_prerequisite schema_errs={bad_errs}")
    if not bad_errs:
        print("FAILED:CNF-0143-probe2 empty prerequisite accepted (completeness hole)")
        return 1

    ws = copy.deepcopy(bad)
    ws["prerequisite"] = "   "
    ws_errs = A.validate_record_schema(ws)
    print(f"whitespace_prerequisite schema_errs={ws_errs}")
    if not ws_errs:
        print("FAILED:CNF-0143-probe2 whitespace prerequisite accepted")
        return 1

    raised = False
    try:
        A.compute_rates([bad] + [r for r in good if r["claim_id"] != "CLAIM-A5"], frame)
    except A.AccountingError as exc:
        raised = "empty prerequisite" in str(exc)
        print(f"compute_rates_rejects_empty={raised} err={exc}")
    if not raised:
        print("FAILED:CNF-0143-probe2 compute_rates accepted empty prerequisite")
        return 1

    if not SCHEMA.is_file():
        print("FAILED:CNF-0143-probe2 program-gate-report schema missing")
        return 1
    if not OVERLAY.is_file():
        print("FAILED:CNF-0143-probe2 completeness overlay schema missing")
        return 1
    validator = A.overlay_validator()
    bogus = {
        "unit_id": "CNF-0143",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0143",
        "question": "x" * 40,
        "tests": [
            {"id": "t1", "command": "python3 -B x.py", "result": "PASS"},
            {"id": "t2", "command": "python3 -B y.py", "result": "PASS"},
        ],
        "reviewer": {"reviewer_id": "r1", "verdict": "PASS", "independent": True},
        "artifacts": [
            {"path": "command-center/receipts/CNF-0143.json", "exists": True, "role": "primary"}
        ],
        "blocked": [
            {
                "claim_id": "CLAIM-A5",
                "prerequisite": "",
                "unblock_experiment": "named experiment text here",
            }
        ],
    }
    gate_errs = [e.message for e in validator.iter_errors(bogus)]
    print(f"report_schema_empty_prereq_errs={gate_errs[:6]}")
    if not gate_errs:
        print("FAILED:CNF-0143-probe2 report schema accepted empty blocked prerequisite")
        return 1

    if not UNK.is_file():
        print("FAILED:CNF-0143-probe2 UNKNOWNS-REGISTER.md missing")
        return 1
    md = UNK.read_text(encoding="utf-8")
    accounted = A.compute_rates(good, frame)
    chk = A.crosscheck_unknowns(accounted["blocked"], md)
    print(f"unknowns_crosscheck ok={chk['ok']} missing={chk['missing']}")
    if not chk["ok"]:
        print("FAILED:CNF-0143-probe2 BLOCKED prerequisite not in UNKNOWNS-REGISTER.md")
        return 1
    planted = A.crosscheck_unknowns(
        [
            {
                "claim_id": "PLANTED",
                "prerequisite": PLANTED,
                "unblock_experiment": "planted-absent control",
            }
        ],
        md,
    )
    if planted["ok"] or not planted["missing"]:
        print("FAILED:CNF-0143-probe2 planted-absent prerequisite was found (detector blind)")
        return 1
    print(f"planted_absent_detected={True} token={PLANTED}")

    sid_a = bundle["expected"]["stratum_a"]
    hand = R.hand_recompute(good, frame, sid_a)
    code_row = [s for s in accounted["strata"] if s["stratum_id"] == sid_a][0]
    if hand["rate_with_blocked_in_denominator"] != code_row["rate_with_blocked_in_denominator"]["as_string"]:
        print("FAILED:CNF-0143-probe2 reviewer with mismatch")
        return 1
    if hand["rate_without_blocked"] != code_row["rate_without_blocked"]["as_string"]:
        print("FAILED:CNF-0143-probe2 reviewer without mismatch")
        return 1
    print(
        f"reviewer_hand stratum={sid_a} with={hand['rate_with_blocked_in_denominator']} "
        f"without={hand['rate_without_blocked']}"
    )

    if not ART.is_file():
        print("FAILED:CNF-0143-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    art_blocked = A.artifact_blocked(doc)
    if len(art_blocked) < 1:
        print("FAILED:CNF-0143-probe2 artifact has no BLOCKED entries")
        return 1
    for entry in art_blocked:
        if not str(entry.get("prerequisite") or "").strip():
            print(f"FAILED:CNF-0143-probe2 artifact BLOCKED {entry.get('claim_id')} empty prerequisite")
            return 1
        if str(entry.get("prerequisite")) not in md:
            print(f"FAILED:CNF-0143-probe2 artifact prerequisite missing from register: {entry.get('prerequisite')}")
            return 1
    art_errs = [e.message for e in validator.iter_errors(doc)]
    if art_errs:
        print("FAILED:CNF-0143-probe2 artifact schema", art_errs[:8])
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-completeness",
                "unit_id": "CNF-0143",
                "empty_prerequisite_rejected": True,
                "whitespace_prerequisite_rejected": True,
                "unknowns_crosscheck_ok": True,
                "planted_absent_detected": True,
                "reviewer_match": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0143-probe2 completeness and UNKNOWNS-REGISTER cross-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
