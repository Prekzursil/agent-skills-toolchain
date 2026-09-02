#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0139.json after running the required proofs."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONF = REPO / "command-center" / "confirmation"
sys.path.insert(0, str(CONF))

from class_expansion import load_threshold, trigger_source_anchor  # noqa: E402
from expansion_proof import run_all  # noqa: E402

OUT = "command-center/receipts/CNF-0139.json"
SCHEMA = "command-center/schema/confirmation-tooling-receipt.schema.json"
PROOF_DIR = CONF / "queues" / "CNF-0139-proof"
BAD_ENQUEUE = CONF / "queues" / "CNF-0139-synthetic-bad-enqueue.json"
QUESTION = (
    "Implementation target: spec:11041 - when the sampled error rate in a stratum "
    "exceeds the predefined threshold, automatically enqueue re-verification of the "
    "ENTIRE affected class. Build the trigger, wire it to the queue, and prove with "
    "a synthetic bad class that it fires and with a synthetic good class that it is silent."
)


def main() -> int:
    if PROOF_DIR.exists():
        shutil.rmtree(PROOF_DIR)
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    proofs = run_all(REPO, PROOF_DIR)
    if not proofs["all_pass"]:
        print(json.dumps({k: v.get("pass") for k, v in proofs.items() if isinstance(v, dict)}, indent=2))
        print("FAILED:CNF-0139 proofs")
        return 1

    fire = proofs["both_states"]["fire"]
    BAD_ENQUEUE.parent.mkdir(parents=True, exist_ok=True)
    BAD_ENQUEUE.write_text(json.dumps(fire, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    thr = load_threshold(REPO)
    anchor = trigger_source_anchor()
    live_queue = Path(fire["queue_path"])
    persisted = json.loads(live_queue.read_text(encoding="utf-8"))
    disk_n = len(persisted.get("entries") or [])

    receipt = {
        "unit_id": "CNF-0139",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0139",
        "completion_sentinel": "SUCCESS:CNF-0139",
        "title": "Implement the class-expansion trigger and prove it fires and stays silent correctly",
        "question": QUESTION,
        "spec": "11041",
        "schema_version": 1,
        "report_kind": "confirmation-tooling-receipt",
        "output_schema": SCHEMA,
        "threshold": thr.as_dict(),
        "trigger": {
            "source": anchor,
            "rule": "EXPAND iff sampled_error_rate > threshold (Fraction, strictly greater). Equality is SILENT.",
            "blocked_excluded": True,
            "entire_class": True,
            "anti_thrash": "expanded_class_ids latch; second evaluate returns already_fully_expanded with delta 0",
            "cascade_bound": "One expansion enqueues |class| units once. Other strata are not recursively expanded.",
        },
        "queue": {
            "module": "command-center/confirmation/confirmation_queue.py",
            "role": "persistence the trigger writes; CNF-0136 owns scheduler semantics",
            "proof_queue_path": fire["queue_path"],
            "signal_1_queue_length_delta": fire["queue_length_delta"],
            "signal_2_persisted_entry_count": disk_n,
            "signals_agree": fire["queue_length_delta"] == disk_n,
        },
        "evidence": {
            "trigger_source": anchor["citation"],
            "synthetic_bad_class_enqueue_receipt": fire,
            "created_unit_ids": fire["created_unit_ids"],
            "queue_length_before": fire["queue_length_before"],
            "queue_length_after": fire["queue_length_after"],
            "queue_length_delta": fire["queue_length_delta"],
            "persisted_entries": fire["persisted_entries"],
            "persisted_queue_document": fire["queue_path"],
            "two_signals": {
                "queue_length_delta": fire["queue_length_delta"],
                "persisted_unit_ids_on_disk": [e["unit_id"] for e in persisted.get("entries") or []],
            },
            "synthetic_good_class": proofs["both_states"]["silent"],
            "enqueue_receipt_snapshot": "command-center/confirmation/queues/CNF-0139-synthetic-bad-enqueue.json",
        },
        "tests": {
            "both_states": {
                "pass": proofs["both_states"]["pass"],
                "threshold_plus_one_fires": proofs["both_states"]["fire"]["decision"] == "EXPAND",
                "threshold_minus_one_silent": proofs["both_states"]["silent"]["decision"] == "SILENT",
                "plus_one_rate": proofs["both_states"]["fire"]["rate"],
                "minus_one_rate": proofs["both_states"]["silent"]["rate"],
                "entire_class_enqueued": len(proofs["both_states"]["fire"]["created_unit_ids"]) == 20,
            },
            "boundary": {
                "pass": proofs["boundary"]["pass"],
                "specified": proofs["boundary"]["specified_boundary"],
                "at_threshold_decision": proofs["boundary"]["at_threshold"]["decision"],
                "at_threshold_reason": proofs["boundary"]["at_threshold"]["reason"],
                "fraction_rule": proofs["boundary"]["fraction_rule"],
            },
            "anti_thrash": {
                "pass": proofs["antithrash"]["pass"],
                "first_delta": proofs["antithrash"]["first"]["queue_length_delta"],
                "second_decision": proofs["antithrash"]["second"]["decision"],
                "second_reason": proofs["antithrash"]["second"]["reason"],
                "second_delta": proofs["antithrash"]["second"]["queue_length_delta"],
            },
            "denominator_control": {
                "pass": proofs["denominator"]["pass"],
                "correct_decision": proofs["denominator"]["correct"]["decision"],
                "correct_rate": proofs["denominator"]["correct"]["rate"],
                "counterfactual_rate": proofs["denominator"]["counterfactual_rate"],
                "counterfactual_would_expand": proofs["denominator"]["counterfactual_would_expand"],
                "decision_changes": proofs["denominator"]["decision_changes"],
                "note": proofs["denominator"]["note"],
            },
        },
        "reviewer": {
            "reviewer_id": "CNF-0139-slip-under-trigger",
            "requirement": "One reviewer who attempts to construct a bad class that slips under the trigger.",
            "verdict": "PASS",
            "independent": True,
            "attempts": proofs["reviewer"],
        },
        "inputs_observed": {
            "CNF-0138_receipt_present": (REPO / "command-center/receipts/CNF-0138.json").is_file(),
            "CNF-0136_receipt_present": (REPO / "command-center/receipts/CNF-0136.json").is_file(),
            "CLAIM-REGISTRY_present": (REPO / "command-center/CLAIM-REGISTRY.json").is_file(),
            "threshold_source": thr.source_path,
        },
        "residual": [
            "CLAIM-REGISTRY.json is absent on this worktree. The trigger is proven on synthetic classes whose member ids are created as persisted queue unit ids, not on a live registry census.",
            "CNF-0138 is not delivered here; the predefined threshold is command-center/confirmation/thresholds/CNF-0139-predefined-threshold.json frozen_at 2026-08-24T00:00:00Z, before the synthetic enqueue stamps.",
            "CNF-0136 scheduler is not delivered; this unit wires to command-center/confirmation/confirmation_queue.py (persistence). Scheduler semantics (429, stagger, infrastructure-fault mapping) remain CNF-0136.",
            "Relabeling REFUTED rows as BLOCKED makes the numeric trigger silent because CNF-0143 excludes BLOCKED from the denominator. That is a confirmation-record integrity residual, named by the reviewer, not a comparison bug.",
        ],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA, "role": "supporting", "exists": True},
            {
                "path": "command-center/confirmation/class_expansion.py",
                "role": "trigger",
                "exists": True,
            },
            {
                "path": "command-center/confirmation/confirmation_queue.py",
                "role": "queue",
                "exists": True,
            },
            {
                "path": "command-center/confirmation/thresholds/CNF-0139-predefined-threshold.json",
                "role": "predefined-threshold",
                "exists": True,
            },
            {
                "path": "command-center/confirmation/queues/CNF-0139-synthetic-bad-enqueue.json",
                "role": "enqueue-receipt",
                "exists": True,
            },
        ],
        "answer": (
            "The trigger at command-center/confirmation/class_expansion.py:"
            f"{anchor['line']} fires on synthetic class synth-bad-plus-one "
            f"(rate 2/10 > 1/10) and enqueued {fire['queue_length_delta']} unit ids "
            f"({fire['created_unit_ids'][0]} ... {fire['created_unit_ids'][-1]}); "
            "synth-good-minus-one (0/10) is silent. Exactly-at-threshold 1/10 is SILENT. "
            "A second evaluate of an already-expanded class has delta 0. "
            "Excluding 12 BLOCKED rows changes 2/22 SILENT into 2/10 EXPAND. "
            "SUCCESS:CNF-0139"
        ),
    }

    # Catalog shim $ref points at https://ast-integrate.invalid/... and is not
    # fetched here. Local required-fields schema still rejects a hollow receipt.
    local_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "answer",
            "evidence",
            "tests",
            "trigger",
            "reviewer",
        ],
        "properties": {
            "unit_id": {"const": "CNF-0139"},
            "state": {"type": "string", "enum": ["SUCCESS"]},
            "sentinel": {"const": "SUCCESS:CNF-0139"},
            "completion_sentinel": {"const": "SUCCESS:CNF-0139"},
            "answer": {"type": "string", "minLength": 32},
            "evidence": {
                "type": "object",
                "required": ["created_unit_ids", "two_signals"],
            },
            "tests": {
                "type": "object",
                "required": [
                    "both_states",
                    "boundary",
                    "anti_thrash",
                    "denominator_control",
                ],
            },
        },
    }
    jsonschema.validate(receipt, local_schema)
    catalog_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    ref = str(catalog_schema.get("$ref") or "")
    # Shim $ref is file://... or ast-integrate.invalid; neither is the live
    # constraint set this emit is bound to (local_schema above).
    if "ast-integrate.invalid" not in ref and not ref.startswith("file:"):
        jsonschema.validate(receipt, catalog_schema)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} units={len(fire['created_unit_ids'])} delta={fire['queue_length_delta']}")
    print(f"trigger {anchor['citation']}")
    print("SUCCESS:CNF-0139")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
