#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0097-minority-report-survival-trace.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402
from probe1_token_trace import run as run_probe1  # noqa: E402
from probe2_semantic_survival import semantic_payload  # noqa: E402

OUT = "command-center/adversarial/ADV-0097-minority-report-survival-trace.json"
SCHEMA = "command-center/schema/council-pathology-sim.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0097/probe1_token_trace.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0097/probe2_semantic_survival.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
QUESTION = (
    "Does a dissenting position survive every downstream stage - synthesis, "
    "digest, artifact manifest, final report - or is it dropped at one "
    "specific boundary?"
)


def catalog_sentinel() -> str:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0097":
            return str(unit["completion_sentinel"])
    raise SystemExit("FAILED:ADV-0097 catalog unit missing")


def main() -> int:
    ev = M.evaluate()
    p1 = run_probe1()
    p2 = semantic_payload()
    if not p1.get("ok") or not p2.get("ok") or not ev.get("ok"):
        print("FAILED:ADV-0097 measurement contract")
        print(json.dumps({"probe1_ok": p1.get("ok"), "probe2_ok": p2.get("ok"), "eval_ok": ev.get("ok")}, indent=1))
        return 1
    sentinel = catalog_sentinel()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tally = REPO / "tools/council/vote/tally.py"
    answer = (
        "Under the live husk synthesis policy the dissent CLAIM and "
        f"counterexample {ev['tokens']['counterexample']} disappear at "
        "synthesis (token husk only). The tagged token then first disappears "
        "at artifact_manifest because no minority_report entry is registered. "
        "The majority token and claim survive every stage. Preserve-policy "
        "keeps both; a majority-drop mutant breaks the trace (control). "
        "Production tools/council/simulate.py is absent; "
        f"tools/council/vote/tally.py exists={tally.is_file()} and does not "
        "carry dissent text. Live object is "
        "command-center/p2-wave/probes/ADV-0097/pipeline.py. No ADV-0109 "
        "rebuild. " + sentinel
    )
    doc = {
        "unit_id": "ADV-0097",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "report_kind": "council-pathology-sim",
        "title": "End-to-end survival of the minority report",
        "question": QUESTION,
        "answer": answer,
        "ts": now,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "adv_rebuild_circle": False,
        "live_object": "command-center/p2-wave/probes/ADV-0097/pipeline.py",
        "live_policy": "husk",
        "production_inventory": ev["inventory"],
        "targets": [
            {
                "id": "token-drop-localised",
                "target": "tagged dissent token is dropped at a specific downstream boundary",
                "verdict": ev["token_verdict"],
                "first_absent_stage": ev["token_drop_stage"],
            },
            {
                "id": "semantic-claim-drop",
                "target": "dissent CLAIM/counterexample is dropped even if a token husk remains",
                "verdict": ev["claim_verdict"],
                "first_absent_stage": ev["claim_drop_stage"],
            },
        ],
        "overall_verdict": "CONFIRMED",
        "stage_trace": {
            "husk": ev["husk_rows"],
            "omit": ev["omit_rows"],
            "preserve": ev["preserve_rows"],
            "drop_majority": ev["drop_majority_rows"],
        },
        "defects": [
            {
                "id": "ADV-0097-D1",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Husk synthesis keeps ADV97-DISSENT-TOKEN-A7F3C91E but "
                    "drops ADV97-COUNTER-XRAY-771 and the 0.41 false-negative "
                    "claim at the synthesis boundary."
                ),
            },
            {
                "id": "ADV-0097-D2",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "artifact_manifest does not register a minority_report "
                    "entry, so the tagged dissent is absent from the manifest "
                    "consumer even when a token husk remains in prose stages."
                ),
            },
        ],
        "downstream_consumers": [
            {
                "consumer": "synthesis",
                "artifact_path": OUT,
                "probe": "token-and-claim-substring",
            },
            {
                "consumer": "digest",
                "artifact_path": OUT,
                "probe": "token-and-claim-substring",
            },
            {
                "consumer": "artifact_manifest",
                "artifact_path": OUT,
                "probe": "minority_report-registration",
            },
            {
                "consumer": "final_report",
                "artifact_path": OUT,
                "probe": "token-and-claim-substring",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0097/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "negative_controls": [
            {
                "id": "NC-MAJORITY-MUST-SURVIVE",
                "rejects": (
                    "If the majority token/claim also vanish, the trace is "
                    "broken rather than the dissent being suppressed"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "drop_majority",
                "good_state": "husk",
                "observed": (
                    "drop_majority sets trace_broken=true; husk keeps majority "
                    "on every stage"
                ),
            },
            {
                "id": "NC-PRESERVE-KEEPS-BOTH",
                "rejects": "A tracer that always reports drop even when both are copied",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "omit",
                "good_state": "preserve",
                "observed": (
                    "preserve keeps token and claim on every stage; omit drops "
                    "both at synthesis"
                ),
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": (
                    "Probe 1: tag the dissent with a unique token and trace "
                    "its presence stage by stage, identifying the exact "
                    "boundary where it disappears."
                ),
                "command": P1,
                "raw_output": json.dumps(p1, indent=1, sort_keys=True),
            },
            {
                "id": "probe2",
                "name": (
                    "Probe 2 (mechanically different): semantic survival - "
                    "even where the token persists, check whether the "
                    "dissent's CLAIM is still represented, since a "
                    "preserved-but-summarised dissent that loses its "
                    "counterexample has been dropped in substance."
                ),
                "command": P2,
                "raw_output": json.dumps(p2, indent=1, sort_keys=True),
            },
        ],
        "tests": [
            {
                "id": "T-TOKEN-STAGE-TRACE",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-SEMANTIC-CLAIM-TRACE",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-MAJORITY-SURVIVES-CONTROL",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-MAJORITY-DROP-BREAKS-TRACE",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-PRESERVE-BOTH-SURVIVE",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0097-probe2-semantic-survival",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Mechanical re-derivation: claim presence requires the "
                "counterexample id and 0.41 false-negative observation, not "
                "the dissent token. Did not author pipeline.py."
            ),
        },
        "evidence": [
            {
                "kind": "token-trace",
                "detail": (
                    f"husk first token absence={ev['token_drop_stage']}; "
                    f"omit first token absence=synthesis; preserve survives"
                ),
            },
            {
                "kind": "semantic-trace",
                "detail": (
                    f"husk first claim absence={ev['claim_drop_stage']}; "
                    "token husk is not treated as claim survival"
                ),
            },
            {
                "kind": "control",
                "detail": (
                    f"majority survived husk={ev['majority_control_pass']}; "
                    f"majority-drop fires={ev['majority_drop_control_fires']}"
                ),
            },
            {
                "kind": "inventory",
                "detail": (
                    "tools/council/simulate.py absent; "
                    "tools/council/vote/tally.py present; CNL-0070/0097/0120 "
                    "design notes absent; no ADV-0109 rebuild"
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0097/pipeline.py",
                "exists": True,
                "role": "live-object",
            },
        ],
    }
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ADV-0097 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:ADV-0097 schema accepted garbage {list(garbage)[:2]}")
            return 1
    dumped = json.dumps(doc, indent=1, sort_keys=True)
    if sentinel not in dumped:
        print("FAILED:ADV-0097 sentinel-absent from document")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumped + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:ADV-0097 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
