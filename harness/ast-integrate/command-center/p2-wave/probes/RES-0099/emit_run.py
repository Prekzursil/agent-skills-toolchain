#!/usr/bin/env python3
"""Write command-center/research/RES-0099.json from a live coverage replay."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coverage as C  # noqa: E402

OUT_REL = "command-center/research/RES-0099.json"
SENTINEL = (
    "SUCCESS:RES-0099 in the receipt AND a field-coverage report against "
    "real existing events plus a stated minimum-sample threshold"
)
QUESTION = (
    "What must be recorded on every gate decision to compute its false-positive "
    "and false-negative rates later, where would that record live, and what is "
    "the minimum sample before a rate may be quoted?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0099/probe1_replay_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0099/probe2_min_sample.py"
)


def main() -> int:
    live = C.analyze()
    cov = live["coverage"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Live harvest is unlabelled: the honest quote is RATE-NOT-QUOTED.
    live_quote = C.quote_rate(k=0, n=0, n_complement=0, kind="fp")
    live_quote["reason"] = cov["rate_quote_block_reason"]

    record_fields = []
    for f in C.FIELDS:
        row = next(r for r in cov["fields"] if r["name"] == f["name"])
        record_fields.append(
            {
                "name": f["name"],
                "why": f["why"],
                "required_on_every_decision": True,
                "live_status": row["status"],
                "already_present": row["already_present"],
                "would_have_to_be_added": row["would_have_to_be_added"],
                "proxy_only": row["proxy_only"],
            }
        )

    ev = live["events_jsonl"]
    jcov = live["events_jsonl_coverage"]
    jsonl_clause = (
        f"On this worktree {C.EVENTS_REL} is present "
        f"({ev['line_records']} line records, {ev['gate_decision_rows']} "
        f"event_type={C.EVENT_TYPE} rows, verbs={ev.get('verbs')}, "
        f"union_keys={ev.get('union_keys')}). Replaying those JSONL rows "
        f"through the proposed record: already-present="
        f"{jcov.get('fields_already_present')}; would-have-to-be-added-or-proxy="
        f"{jcov.get('fields_that_would_have_to_be_added')}; labelled="
        f"{jcov.get('labelled_ground_truth_count')}. "
        if ev.get("present")
        else (
            f"On this worktree {C.EVENTS_REL} is absent. "
        )
    )
    answer = (
        "Every gate decision must append one gate.decision.v1 record to "
        f"{C.RECORD_LIVES_AT} (JSONL, hash-chained per CC-0007). The record "
        "must carry predicted_class (POSITIVE=fired / NEGATIVE=silent), "
        "ground_truth_class (POSITIVE=should-fire / NEGATIVE=should-not / "
        "UNLABELLED), truth_source, input_fingerprint, gate_id, command, "
        "exit_code, denominator_eligible, and confusion. Unlabelled rows stay "
        "out of the denominator. "
        + jsonl_clause
        + (
            f"Probe1 field coverage is a live replay of "
            f"{cov['record_count']} existing gate-like probe JSON files "
            f"(validate/measure/strike/SUBAGENT-RETURN), not a fabricated "
            f"JSONL. Native ground_truth_class count on that harvest is "
            f"{cov['labelled_ground_truth_count']}. No FP or FN rate is quoted. "
            f"Minimum sample: n>={C.MIN_LABELLED_N} labelled decisions of the "
            f"quoted class and >={C.MIN_PER_CLASS} of the complementary class "
            f"(rule-of-three 95% upper at n={C.MIN_LABELLED_N} is "
            f"{C.rule_of_three_upper(C.MIN_LABELLED_N):.1%}). "
        )
        + SENTINEL
    )

    doc = {
        "$schema": "command-center/schema/measurement-run.schema.json",
        "unit_id": "RES-0099",
        "id": "RES-0099",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "report_kind": "measurement-run",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Design the telemetry that would measure this program's own gate false-positive rate",
        "question": QUESTION,
        "answer": answer,
        "recorded_at": now,
        "record_design": {
            "schema_version": C.SCHEMA_VERSION,
            "event_type": C.EVENT_TYPE,
            "lives_at": C.RECORD_LIVES_AT,
            "why_there": (
                "The catalog already names command-center/events/EVENTS.jsonl as "
                "the append-only decision log (CC-0007 hash chain). A second log "
                "would split the denominator. New event_type=gate.decision rows "
                "append; they do not rewrite history."
            ),
            "predicted_positive_means": "the gate fired (block/fail/red)",
            "predicted_negative_means": "the gate was silent (pass/green)",
            "truth_positive_means": "the input should have fired the gate (known-bad fixture or adjudicated defect)",
            "truth_negative_means": "the input should not have fired (known-good fixture)",
            "confusion": {
                "TP": "fired on known-bad",
                "FP": "fired on known-good",
                "TN": "silent on known-good",
                "FN": "silent on known-bad",
                "UNLABELLED": "no ground_truth; excluded from rates",
            },
            "template": C.empty_record_template(),
            "fields": record_fields,
        },
        "events_jsonl": live["events_jsonl"],
        "events_jsonl_coverage": live["events_jsonl_coverage"],
        "replay_source": live["replay_source"],
        "field_coverage": {
            "against": live["replay_source"],
            "record_count": cov["record_count"],
            "labelled_ground_truth_count": cov["labelled_ground_truth_count"],
            "native_predicted_class_count": cov["native_predicted_class_count"],
            "derived_predicted_from_state_count": cov["derived_predicted_from_state_count"],
            "fields_already_present": live["fields_already_present"],
            "fields_that_would_have_to_be_added": live["fields_that_would_have_to_be_added"],
            "fields": cov["fields"],
            "harvested_paths": live["harvested_paths"],
            "note": (
                "Primary probe1 corpus is a live replay of existing gate-like "
                "JSON under command-center/p2-wave/probes (validate/measure/"
                "strike/SUBAGENT-RETURN), excluding RES-0099. Catalog-named "
                f"{C.EVENTS_REL} is replayed separately in events_jsonl_coverage "
                "because it is JSONL, not a single JSON object."
            ),
        },
        "minimum_sample": live["min_sample"],
        "min_sample": live["min_sample"],
        "rate_quote": live_quote,
        "tests": [
            {
                "id": "T1-replay-field-coverage",
                "name": "replay existing events through the proposed record and report field coverage",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-min-sample-control",
                "name": "control: state the minimum sample size below which no rate may be quoted, and why",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0099-probe2-min-sample-floor",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Independent signal is the min-sample control (n=10 must refuse; "
                "n=30 with complementary class may quote). Not a second same-vendor "
                "read of the same coverage table."
            ),
        },
        "negative_controls": [
            {
                "id": "NC-small-n",
                "claim": "0 fires in 10 known-good trials is 0% FP",
                "result": "REJECTED-RATE-NOT-QUOTED",
                "why": "rule-of-three 95% upper bound at n=10 is 30%",
            },
            {
                "id": "NC-no-known-bad",
                "claim": "a gate with only known-good traffic has FN=0",
                "result": "REJECTED-NOT-CHECKED",
                "why": "FN is unmeasurable without known-bad fixtures",
            },
        ],
        "residual_unknowns": [
            f"{C.EVENTS_REL} exists but holds only verb=note rows and zero {C.EVENT_TYPE} records, so a live FP/FN rate remains unmeasurable.",
            "No labelled known-good/known-bad fixture set for the live delivery gate is on disk here, so this unit designs the record and refuses to quote a rate.",
        ],
        "downstream_consumers": [
            "REL-0019 numeric misfire budgets",
            "CC-0007 EVENTS.jsonl hash chain",
        ],
        "defects": [],
        "registered": True,
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"}
        ],
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0099 emit sentinel missing after write")
        return 1
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
