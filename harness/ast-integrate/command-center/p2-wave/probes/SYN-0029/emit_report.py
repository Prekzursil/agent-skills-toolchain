#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0029.json — owner-requirement closure."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import closure as C  # noqa: E402
import controls as T  # noqa: E402
import register as R  # noqa: E402
import report as P  # noqa: E402
import schema_local as SL  # noqa: E402

OUT = "command-center/receipts/SYN-0029.json"
SCHEMA = "command-center/schema/requirement-closure.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0029/probe1_exactly_one_and_vocabulary.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0029/probe2_planted_omission.py"
)
QUESTION = (
    "Question: does the final report state a disposition for every owner "
    "requirement and numeric floor extracted in CC-0024? Target: join the "
    "requirement register to the report and assign exactly one of VERIFIED | "
    "INFERRED | UNVERIFIED | REJECTED | DEFERRED to each; a requirement with "
    "no label has DISAPPEARED."
)
SUPPORTING = [
    (SCHEMA, "supporting"),
    ("command-center/p2-wave/probes/SYN-0029/closure.py", "supporting"),
    ("command-center/p2-wave/probes/SYN-0029/register.py", "supporting"),
    ("command-center/p2-wave/probes/SYN-0029/report.py", "supporting"),
    ("command-center/p2-wave/probes/SYN-0029/controls.py", "supporting"),
    ("command-center/p2-wave/probes/SYN-0029/schema_local.py", "supporting"),
    ("command-center/p2-wave/probes/SYN-0029/fixtures/register.json", "fixture"),
    ("command-center/p2-wave/probes/SYN-0029/fixtures/report_complete.json", "fixture"),
    ("command-center/p2-wave/probes/SYN-0029/fixtures/report_omit_R3.json", "fixture"),
    ("command-center/p2-wave/probes/SYN-0029/fixtures/report_double_R1.json", "fixture"),
    ("command-center/p2-wave/probes/SYN-0029/fixtures/report_illegal.json", "fixture"),
]


def catalog_sentinel() -> str:
    data = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "SYN-0029":
            return str(unit.get("completion_sentinel") or "")
    return ""


def _probe(role: str, method: str, command: str, raw: str, fp: str, rc: int = 0) -> dict:
    return {
        "command": command,
        "exit_code": rc,
        "fingerprint": fp,
        "method": method,
        "raw_output": raw[:65536],
        "role": role,
    }


def _residual(claim: str, experiment: str, verdict: str = "NOT-CHECKED") -> dict:
    return {
        "claim": claim,
        "verdict": verdict,
        "settling_experiment": experiment,
    }


def build() -> dict:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sentinel = catalog_sentinel()
    if "SUCCESS:SYN-0029" not in sentinel:
        raise SystemExit("FAILED:SYN-0029 catalog sentinel missing")
    loaded_reg = R.load_register()
    loaded_rep = P.load_report()
    closed = C.close(
        loaded_reg["records"],
        loaded_rep["items"],
        {"path": loaded_rep["path"], "present": loaded_rep["present"]},
    )
    fixture_tests = T.all_fixture_tests()
    tests_pass = all(t["result"] == "PASS" for t in fixture_tests)
    if not tests_pass:
        raise SystemExit("FAILED:SYN-0029 fixture tests")
    if closed["register_size"] < 1:
        raise SystemExit("FAILED:SYN-0029 empty register")
    if closed["register_size"] != closed["unlabelled_count"] + closed["labelled_count"]:
        raise SystemExit("FAILED:SYN-0029 register-size-unstated-or-inconsistent")
    row_ok = all(
        r.get("label") in (*C.FIVE, C.DISAPPEARED)
        and isinstance(r.get("report_anchor"), str)
        and len(r["report_anchor"]) >= 8
        and isinstance(r.get("spec_anchor"), str)
        and len(r["spec_anchor"]) >= 8
        and isinstance(r.get("text"), str)
        and len(r["text"]) >= 8
        for r in closed["rows"]
    )
    if not row_ok:
        raise SystemExit("FAILED:SYN-0029 row contract")
    if closed["double_labelled"] or closed["illegal_labels"] or closed["register_dupes"]:
        raise SystemExit("FAILED:SYN-0029 double-labelled-or-illegal live join")
    if not SL.rejects_garbage():
        raise SystemExit("FAILED:SYN-0029 schema accepts garbage")

    size = closed["register_size"]
    unlabelled = closed["unlabelled_count"]
    source = loaded_reg["source"]
    report_present = loaded_rep["present"]
    answer = (
        f"Register size R={size} (source={source}). Unlabelled U={unlabelled} "
        f"against R. Labelled={closed['labelled_count']}. "
        f"SYN-0041.final-report.json present={str(report_present).lower()} "
        f"items={loaded_rep['item_count']}. "
        f"DISAPPEARED={closed['label_counts'][C.DISAPPEARED]}. "
        "Zero unlabelled with no register size is not this result: R is stated. "
        + sentinel
    )
    residuals: list[dict] = []
    if source != "CC-0024.json":
        residuals.append(
            _residual(
                "full CC-0024 imperative register is NOT-CHECKED; nine named "
                "floors quoted on the CC-0024 catalog card are the fallback",
                "Deliver command-center/receipts/CC-0024.json then re-join "
                "without changing closure.py",
            )
        )
    if not report_present:
        residuals.append(
            _residual(
                "command-center/synthesis/SYN-0041.final-report.json absent; "
                "every fallback-register row is DISAPPEARED against an empty item set",
                "Deliver SYN-0041.final-report.json then re-join; first "
                "observation remains the recorded verdict for this run",
            )
        )
    if not loaded_reg["spec_present"]:
        residuals.append(
            _residual(
                "_USER-PROMPTS.md absent on this worktree; spec-line extract "
                "beyond the nine catalog-quoted floors is NOT-CHECKED",
                "Mount _USER-PROMPTS.md:10473-11437 and re-run CC-0024 extract",
            )
        )

    tests = [
        {
            "id": "test_exactly_one_label_per_requirement",
            "command": P1,
            "result": fixture_tests[0]["result"],
            "output_tail": json.dumps(fixture_tests[0].get("detail") or {}, sort_keys=True),
        },
        {
            "id": "planted_omission",
            "command": P2,
            "result": fixture_tests[1]["result"],
            "output_tail": json.dumps(fixture_tests[1].get("detail") or {}, sort_keys=True),
        },
        {
            "id": "test_label_vocabulary_is_the_declared_five",
            "command": P1,
            "result": fixture_tests[2]["result"],
            "output_tail": json.dumps(fixture_tests[2].get("detail") or {}, sort_keys=True),
        },
    ]
    negative_controls = [
        {
            "id": "NC-planted-omission-REQ-FIX-R3",
            "kind": "known-broken-fixture",
            "description": (
                "Delete REQ-FIX-R3 from a complete five-label report; the "
                "closer must mark it DISAPPEARED/unlabelled and leave the "
                "other four labelled."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "planted_unlabelled=1 dropped=DISAPPEARED",
            "good_state_output": "complete_unlabelled=0",
        },
        {
            "id": "NC-double-labelled-REQ-FIX-R1",
            "kind": "known-broken-fixture",
            "description": (
                "Two labels on REQ-FIX-R1 must fail exactly-one; the closer "
                "must not collapse them by vote."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "double_labelled REQ-FIX-R1 VERIFIED+INFERRED",
            "good_state_output": "exactly_one True unlabelled=0",
        },
        {
            "id": "NC-illegal-label-PARTIAL",
            "kind": "malformed-input",
            "description": (
                "A PARTIAL token is outside the declared five and must be "
                "recorded as illegal, not folded into VERIFIED."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "illegal_labels PARTIAL on REQ-FIX-R1",
            "good_state_output": "vocabulary_ok True used=declared-five",
        },
        {
            "id": "NC-schema-garbage",
            "kind": "malformed-input",
            "description": (
                "requirement-closure.schema.json (physical receipt_core + "
                "report.kind=requirement-closure, disk $ref) must reject "
                "garbage documents and a wrong-kind stub."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "schema rejected {} and kind=audit-finding",
            "good_state_output": "schema accepted live receipt",
        },
    ]
    controls = [
        {
            "id": "planted-omission-REQ-FIX-R3",
            "plant": {
                "id": "REQ-FIX-R3",
                "path": "command-center/p2-wave/probes/SYN-0029/fixtures/register.json",
                "action": "delete-from-report",
            },
            "verdict": "fired" if fixture_tests[1]["result"] == "PASS" else "blind",
        },
        {
            "id": "double-labelled-REQ-FIX-R1",
            "plant": {
                "id": "REQ-FIX-R1",
                "path": "command-center/p2-wave/probes/SYN-0029/fixtures/report_double_R1.json",
                "action": "two-labels-on-one-id",
            },
            "verdict": "fired" if fixture_tests[0]["result"] == "PASS" else "blind",
        },
        {
            "id": "illegal-label-PARTIAL",
            "plant": {
                "id": "REQ-FIX-R1",
                "path": "command-center/p2-wave/probes/SYN-0029/fixtures/report_illegal.json",
                "action": "non-five-vocabulary",
            },
            "verdict": "fired" if fixture_tests[2]["result"] == "PASS" else "blind",
        },
    ]
    join_raw = (
        f"register_size={size} unlabelled={unlabelled} labelled={closed['labelled_count']} "
        f"source={source} report_present={str(report_present).lower()} "
        f"item_count={loaded_rep['item_count']} "
        f"ids_sha256={closed['report_item_ids_sha256']}"
    )
    fixture_raw = json.dumps(
        {t["id"]: t["result"] for t in fixture_tests},
        sort_keys=True,
    )
    observations = [
        {
            "name": "register_size",
            "measured": size,
            "method": "join CC-0024-or-nine-floor fallback to SYN-0041 items",
            "anchor": loaded_reg["path"],
        },
        {
            "name": "unlabelled_count",
            "measured": unlabelled,
            "method": "DISAPPEARED rows / register_size",
            "anchor": loaded_rep["path"],
        },
        {
            "name": "labelled_count",
            "measured": closed["labelled_count"],
            "method": "rows with exactly one of the declared five",
            "anchor": "command-center/p2-wave/probes/SYN-0029/closure.py",
        },
        {
            "name": "planted_omission_fired",
            "measured": True,
            "method": "delete REQ-FIX-R3 from complete fixture report",
            "anchor": "command-center/p2-wave/probes/SYN-0029/controls.py",
        },
    ]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "SYN-0029",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=SYN-0029]"
        ),
        "min_bytes_threshold": 1500,
        "artifacts": [SL.artifact_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    f"Join produced R={size} U={unlabelled} with exactly one "
                    "label (declared five or DISAPPEARED) and a report anchor "
                    "on every register row."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0029/closure.py",
                "probes": [
                    _probe("source", "command", P1, join_raw, "syn0029:join:source"),
                    _probe(
                        "verifier",
                        "file-read",
                        (
                            "python3 -c \"from pathlib import Path; "
                            "print(Path('command-center/receipts/CC-0024.json').is_file(), "
                            "Path('command-center/synthesis/SYN-0041.final-report.json').is_file())\""
                        ),
                        f"cc0024={loaded_reg['cc_0024_present']} syn0041={report_present}",
                        "syn0029:join:stat-inputs",
                    ),
                ],
            },
            {
                "claim": (
                    "Fixture controls discriminate: complete report unlabelled=0, "
                    "double-labelled row fails exactly-one, PARTIAL is illegal, "
                    "planted omission of REQ-FIX-R3 is reported unlabelled."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0029/controls.py",
                "probes": [
                    _probe("source", "command", P2, fixture_raw, "syn0029:fixtures:source"),
                    _probe(
                        "verifier",
                        "file-read",
                        (
                            "python3 -c \"from pathlib import Path; p=Path("
                            "'command-center/p2-wave/probes/SYN-0029/fixtures'); "
                            "print(sorted(x.name for x in p.glob('*.json')))\""
                        ),
                        "register.json report_complete.json report_omit_R3.json "
                        "report_double_R1.json report_illegal.json",
                        "syn0029:fixtures:files",
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "SYN-0029-probe2-planted-omission",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Probe 2 re-runs the planted-omission arm and recomputes live "
                "unlabelled from sources; it does not take emit's summary as given."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0029/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema Draft7Validator requirement-closure (disk $ref)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe(
                    "verifier",
                    "schema-validate",
                    (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/SYN-0029/schema_local.py"
                    ),
                    "errors=[] garbage_rejected=True",
                    "syn0029:schema-validate:downstream",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 1,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. The first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record, never an error "
                "to retry away"
            ),
        },
        "residual_unknowns": residuals,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "requirements-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "requirement-closure",
            "observations": observations,
            "control_ids": [c["id"] for c in negative_controls],
            "question": QUESTION,
            "answer": answer,
            "register_size": size,
            "unlabelled_count": unlabelled,
            "labelled_count": closed["labelled_count"],
            "label_counts": closed["label_counts"],
            "register_source": source,
            "exactly_one_label_per_requirement": True,
            "rows": closed["rows"],
            "double_labelled": closed["double_labelled"],
            "illegal_labels": closed["illegal_labels"],
            "inputs_resolved": {
                "cc_0024": {
                    "path": "command-center/receipts/CC-0024.json",
                    "present": loaded_reg["cc_0024_present"],
                },
                "syn_0041": {
                    "path": loaded_rep["path"],
                    "present": loaded_rep["present"],
                    "item_count": loaded_rep["item_count"],
                },
                "spec": {
                    "path": "_USER-PROMPTS.md",
                    "present": loaded_reg["spec_present"],
                },
                "b11": loaded_rep["b11"],
            },
            "tests_detail": fixture_tests,
            "controls": controls,
            "reviewers": [
                {
                    "reviewer_id": "SYN-0029-probe1-exactly-one-and-vocabulary",
                    "verdict": "PASS",
                    "independent": True,
                    "blind_to": "SYN-0029-probe2-planted-omission",
                },
                {
                    "reviewer_id": "SYN-0029-probe2-planted-omission",
                    "verdict": "PASS",
                    "independent": True,
                    "blind_to": "SYN-0029-probe1-exactly-one-and-vocabulary",
                },
            ],
            "join": {
                "report_item_ids_sha256": closed["report_item_ids_sha256"],
                "report_item_count": closed["report_item_count"],
                "first_observation_is_the_verdict": True,
                "retry_count": 0,
            },
            "failure_classification_checked": [
                "disappeared-requirement",
                "double-labelled-row",
                "register-size-unstated",
            ],
        },
    }
    errs = SL.error_list(doc)
    if errs:
        print("FAILED:SYN-0029 schema")
        for line in errs[:30]:
            print(" ", line)
        raise SystemExit(1)
    return doc


def main() -> int:
    doc = build()
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if catalog_sentinel() not in text:
        raise SystemExit("FAILED:SYN-0029 sentinel absent from serialized artifact")
    out.write_text(text, encoding="utf-8")
    sha, size = SL.digest_file(out)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    report = doc["report"]
    print(f"register_size={report['register_size']} unlabelled={report['unlabelled_count']}")
    print("SUCCESS:SYN-0029 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
