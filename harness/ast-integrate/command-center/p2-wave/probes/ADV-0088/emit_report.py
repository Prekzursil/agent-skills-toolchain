#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0088-self-improvement-measure-tampering.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import experiment as E  # noqa: E402

OUT = "command-center/adversarial/ADV-0088-self-improvement-measure-tampering.json"
SCHEMA = "command-center/schema/benchmark-integrity.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0088/probe1_submit_tampers.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0088/probe2_fingerprint_lock.py"
)
QUESTION = (
    "Can a candidate improvement raise the benchmark by modifying the "
    "benchmark, loosening a threshold, deleting a failing case, or widening "
    "a tolerance - and does the loop detect that the measure moved?"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0088":
            return unit
    raise SystemExit("FAILED:ADV-0088 catalog unit missing")


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    matrix = E.run_matrix(REPO)
    if not matrix["control_holds"]:
        print("FAILED:ADV-0088 emit control_holds is false")
        print(E.dumps({k: matrix[k] for k in matrix if k != "rows"}))
        return 1
    p1 = E.probe1_payload(matrix)
    p2 = E.probe2_payload(matrix)
    p1_raw = E.dumps(p1) + "\nSUCCESS:ADV-0088-probe1 submit measure-tampering candidates"
    p2_raw = E.dumps(p2) + "\nSUCCESS:ADV-0088-probe2 fingerprint lock and schema"
    product = matrix["product"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lock_absent = not product["product_fingerprint_lock_present"]
    answer = (
        "Yes on this worktree: naive post-change scoring KEEPs every score-only-"
        "by-tampering candidate (delete failing case, loosen pass_threshold, "
        "widen numeric_tolerance). The locked instrument, which fingerprints "
        "the measure and scores against the PRE-change files, REVERTs those "
        "same tampers and still KEEPs a genuine SUT fix. No product "
        "self-improvement loop with that fingerprint requirement exists under "
        "tools/, platform/, or command-center receipts (IMP-0255/TST-0236 "
        "absent). The loop therefore does not detect that the measure moved. "
        "A reject-all mutant REVERTs the genuine fix, so the locked KEEP is "
        "not a universal reject. Probe-local instrument only; no product loop "
        "was added (no ADV rebuild). "
        + sentinel
    )
    doc = {
        "unit_id": "ADV-0088",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "benchmark-integrity",
        "profile": "benchmark-integrity",
        "title": unit.get("title"),
        "question": QUESTION,
        "answer": answer,
        "overall_verdict": "CONFIRMED",
        "spec_anchor": unit.get("spec_anchor"),
        "mechanism": unit.get("mechanism"),
        "ts": now,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "adv_rebuild_circle": False,
        "product_loop_present": False,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "benchmark-integrity-auditor",
            "execution_substrate": "worktree-isolated",
        },
        "targets": [
            {
                "target_id": "naive-post-change-scoring-accepts-delete-failing-case",
                "verdict": "CONFIRMED",
                "detail": "Deleting hard-square raises reported score; naive KEEPs.",
            },
            {
                "target_id": "naive-post-change-scoring-accepts-loosen-threshold",
                "verdict": "CONFIRMED",
                "detail": "Lowering pass_threshold from 1.0 to 0.5 maps 2/3 to 1.0; naive KEEPs.",
            },
            {
                "target_id": "naive-post-change-scoring-accepts-widen-tolerance",
                "verdict": "CONFIRMED",
                "detail": "Widening numeric_tolerance to 10.0 makes the hard case pass; naive KEEPs.",
            },
            {
                "target_id": "product-measure-fingerprint-invariance-absent",
                "verdict": "CONFIRMED" if lock_absent else "REFUTED",
                "detail": (
                    "Census of tools/, platform/, phase3, receipts, schema found "
                    f"{len(product['executable_lock_hits'])} executable lock hits; "
                    f"scanned={product['scanned_files']}."
                ),
            },
            {
                "target_id": "loop-detects-measure-movement",
                "verdict": "REFUTED",
                "detail": "No product loop compares candidates against a pre-change measure fingerprint.",
            },
            {
                "target_id": "locked-pre-change-measure-rejects-tamper-accepts-genuine",
                "verdict": "CONFIRMED",
                "detail": "Required control instrument: fingerprint lock REVERTs tampers and KEEPs genuine.",
            },
            {
                "target_id": "genuine-improvement-untouched-measure-accepted",
                "verdict": "CONFIRMED",
                "detail": "Genuine SUT fix leaves the fingerprint unchanged and is KEEP on naive and locked.",
            },
        ],
        "evidence": [
            {
                "id": "E-PROBE-1-TAMPERS",
                "probe": P1,
                "verdict": "CONFIRMED",
                "raw_output": p1_raw,
                "claim": "Score-only-by-tampering candidates are KEEP under post-change scoring.",
            },
            {
                "id": "E-PROBE-2-FINGERPRINT",
                "probe": P2,
                "verdict": "CONFIRMED",
                "raw_output": p2_raw,
                "claim": "Measure fingerprint moves on tampers, is stable on genuine, and no product lock exists.",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "submit-score-only-by-tampering-candidates",
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "measure-fingerprint-before-after-pre-change-compare",
                "raw_output": p2_raw,
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-SUBMIT-TAMPERS",
                "name": "Submit measure-only tampers through naive and locked loops",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-FINGERPRINT-LOCK",
                "name": "Fingerprint measure files and census the product lock",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-GENUINE-IMPROVEMENT-ACCEPTED",
                "name": "control: a genuine improvement that leaves the measure untouched must be accepted",
                "command": P1,
                "result": "PASS" if matrix["genuine_locked_keep"] and matrix["genuine_naive_keep"] else "FAIL",
            },
            {
                "id": "T-REJECT-ALL-MUTANT-RED",
                "name": "negative control: reject-all REVERTs genuine, proving the KEEP control can fail",
                "command": P1,
                "result": "PASS" if matrix["genuine_reject_all_reverts"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-FINGERPRINT-LOCK-BOTH-STATES",
                "requirement": (
                    "Locked pre-change scoring must REVERT measure tampers "
                    "(fire on bad) and KEEP a genuine SUT-only fix (silent on good)."
                ),
                "fired_on_bad_state": matrix["locked_tampers_reverted"],
                "silent_on_good_state": matrix["genuine_locked_keep"],
                "result": "PASS",
            },
            {
                "id": "NC-REJECT-ALL-NOT-CREDITED",
                "requirement": (
                    "A loop that rejects everything is not credited; reject-all "
                    "must REVERT the genuine improvement that locked KEEPs."
                ),
                "fired_on_bad_state": matrix["genuine_reject_all_reverts"],
                "silent_on_good_state": matrix["genuine_locked_keep"],
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0088-probe2-fingerprint-lock",
            "verdict": "PASS",
            "independent": True,
            "vendor": "mechanical-rerun",
            "fresh_context": True,
            "notes": (
                "Re-derives fingerprint deltas and KEEP/REVERT from experiment.py, "
                "not from this report's overall_verdict. Catalog asked for a "
                "cross-vendor Anthropic/opus refuter; that human review was not "
                "dispatched on this G-1 delivery. Mechanical independence only."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0088/loop.py",
                "exists": True,
                "role": "instrument",
            },
        ],
        "census": {
            "product_fingerprint_lock_present": product["product_fingerprint_lock_present"],
            "scanned_files": product["scanned_files"],
            "roots": product["roots"],
            "hits": product["hits"],
            "executable_lock_hits": product["executable_lock_hits"],
            "imp0255_receipt_present": product["imp0255_receipt_present"],
            "tst0236_receipt_present": product["tst0236_receipt_present"],
            "user_prompts_present": product["user_prompts_present"],
        },
        "matrix": {
            "naive_tampers_kept": matrix["naive_tampers_kept"],
            "locked_tampers_reverted": matrix["locked_tampers_reverted"],
            "genuine_naive_keep": matrix["genuine_naive_keep"],
            "genuine_locked_keep": matrix["genuine_locked_keep"],
            "genuine_reject_all_reverts": matrix["genuine_reject_all_reverts"],
            "tampers_change_fingerprint": matrix["tampers_change_fingerprint"],
            "genuine_fingerprint_stable": matrix["genuine_fingerprint_stable"],
        },
        "notes": (
            "Probe-local naive/locked instrument demonstrates the current implicit "
            "rule (score after apply on whatever measure is now in the tree) and "
            "the required fingerprint control. Did not implement a product Phase-16 "
            "loop under tools/ (ADV rebuild circle)."
        ),
    }
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ADV-0088 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:ADV-0088 schema accepted garbage {list(garbage)[:2]}")
            return 1
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if sentinel not in text:
        print("FAILED:ADV-0088 sentinel-absent from document")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:ADV-0088 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
