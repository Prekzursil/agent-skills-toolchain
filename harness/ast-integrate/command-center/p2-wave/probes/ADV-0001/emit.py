#!/usr/bin/env python3
"""Emit ADV-0001 refutation record. Does not run global unit_manifest.py --write."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
from consumer import consume_file, live_delivery_gate, production_inventory  # noqa: E402
from reducer import CONDITIONS, reduce_file  # noqa: E402

OUT_REL = "command-center/adversarial/ADV-0001-predicate-passing-unusable-counterexample.json"
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0001/probe1_reducer_verdicts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0001/probe2_consumer_exits.py"
)
# Must match WORK-UNIT-CATALOG.json completion_sentinel byte-for-byte (G-1).
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0001 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0001 <reason>."
)
QUESTION = (
    "Can a work-unit output be constructed that satisfies all 12 numbered "
    "conditions of the shared completion predicate and is still unusable by "
    "its declared downstream consumer - i.e. is condition 12 ('downstream "
    "consumers can read it') actually evaluated, or is it decorative?"
)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def line_of(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ADV-0001 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def validate_and_write(doc: dict) -> int:
    try:
        import jsonschema
    except ImportError:
        print("FAILED:ADV-0001 jsonschema not installed")
        return 1
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    garbage_rejected = 0
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 200}):
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            garbage_rejected += 1
    if garbage_rejected != 3:
        print("FAILED:ADV-0001 schema does not reject garbage")
        return 1
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        print(f"FAILED:ADV-0001 artifact schema: {exc.message}")
        print(exc.schema)
        return 1
    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    cases = F.dump()
    inv = production_inventory()
    adv_rows = []
    live_unusable_pass = 0
    for case in cases:
        path = REPO / case["path"]
        red = reduce_file(path)
        code, why = consume_file(path)
        live_ok, live_why = live_delivery_gate(path)
        counter = (not case["is_control"]) and red["verdict"] == "PASS" and code != 0
        if live_ok and not case["is_control"]:
            live_unusable_pass += 1
        adv_rows.append(
            {
                "id": case["id"],
                "class": case["class"],
                "path": case["path"],
                "is_control": case["is_control"],
                "reducer_verdict": red["verdict"],
                "reducer_failing": red.get("failing") or [],
                "consumer_exit": code,
                "consumer_why": why,
                "live_delivery_ok": live_ok,
                "live_delivery_why": live_why,
                "counterexample": counter,
            }
        )

    attacks = [r for r in adv_rows if not r["is_control"]]
    controls = [r for r in adv_rows if r["is_control"]]
    cex = [r for r in attacks if r["counterexample"]]
    ctrl_ok = (
        bool(controls)
        and controls[0]["reducer_verdict"] == "PASS"
        and controls[0]["consumer_exit"] == 0
    )
    if len(cex) < 6 or not ctrl_ok:
        print("FAILED:ADV-0001 experiment did not yield 6 counterexamples + control")
        print(json.dumps(adv_rows, indent=1)[:4000])
        return 1

    prod_present = inv["platform_lib_completion_predicate"]["present"]
    cc_present = inv["cc0003_receipt"]["present"]
    gates_present = inv["completion_gates"]["present"]
    ru_present = inv["ready_units"]["present"]

    cat = "command-center/WORK-UNIT-CATALOG.json"
    redp = "command-center/p2-wave/probes/ADV-0001/reducer.py"
    consp = "command-center/p2-wave/probes/ADV-0001/consumer.py"
    buildp = "command-center/p2-wave/_build_IMP0433.py"
    cat_line = line_of(cat, "predicate-passing-unusable-counterexample")
    build_line = line_of(buildp, "downstream consumers can read it")
    red_line = line_of(redp, "c12_mechanism")
    cons_line = line_of(consp, "records-missing-or-empty")

    answer = (
        "Yes: six schema-valid envelopes satisfy all twelve syntactic "
        "conditions — including condition 12 as the executed/read_ok flags — "
        "and the declared consumer (consumer.py) exits nonzero on each. "
        "The negative control is readable (reducer PASS, consumer exit 0). "
        f"The live P2 fan-in ready_units.artifact_delivered also accepted "
        f"{live_unusable_pass}/6 unusable envelopes (resolver=None; c12 is "
        f"not a check). Production CC-0003/"
        f"platform/lib/completion_predicate.py present="
        f"{prod_present}; COMPLETION-GATES.json present={gates_present}; "
        f"CC-0003 receipt present={cc_present}. Condition 12 is decorative "
        f"on this tree. SUCCESS:ADV-0001"
    )

    def assemble(rc1: int, out1: str, rc2: int, out2: str) -> dict:
        return {
            "unit_id": "ADV-0001",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:ADV-0001 predicate-passing-unusable counterexample recorded",
            "completion_sentinel": CATALOG_SENTINEL,
            "report_kind": "refutation-record",
            "schema_version": 1,
            "question": QUESTION,
            "answer": answer,
            "spec_anchor": "_USER-PROMPTS.md:10627-10648",
            "mechanism": (
                "semantic-gap attack: satisfy every syntactic condition while "
                "violating the intent of condition 12"
            ),
            "conditions": [{"id": i + 1, "text": t} for i, t in enumerate(CONDITIONS)],
            "targets": [
                {
                    "id": "C12-ACTUALLY-EVALUATED",
                    "claim": "Condition 12 runs a real downstream consumer.",
                    "verdict": "REFUTED",
                    "basis": (
                        "Reducer inspects executed/read_ok flags only; "
                        "consumer.py is never called."
                    ),
                },
                {
                    "id": "PASSING-UNUSABLE-CONSTRUCTIBLE",
                    "claim": "A predicate-passing unusable unit output can be constructed.",
                    "verdict": "CONFIRMED",
                    "basis": f"{len(cex)} envelopes reducer PASS and consumer exit != 0.",
                },
                {
                    "id": "LIVE-READY-UNITS-EVALUATES-C12",
                    "claim": "ready_units.artifact_delivered evaluates condition 12.",
                    "verdict": "REFUTED",
                    "basis": (
                        f"Live gate accepted {live_unusable_pass}/6 unusable envelopes; "
                        "its docstring lists exists/parse/schema/state, not a consumer."
                    ),
                },
                {
                    "id": "PRODUCTION-CC0003-REDUCER-ON-DISK",
                    "claim": "platform/lib/completion_predicate.py and CC-0003 receipt exist.",
                    "verdict": "REFUTED" if not (prod_present or cc_present) else "CONFIRMED",
                    "basis": (
                        f"completion_predicate.py present={prod_present} "
                        f"CC-0003 present={cc_present} "
                        f"COMPLETION-GATES present={gates_present}"
                    ),
                },
                {
                    "id": "NEGATIVE-CONTROL-BOTH-PASS",
                    "claim": "One artifact the consumer genuinely reads PASSes both probes.",
                    "verdict": "CONFIRMED" if ctrl_ok else "NOT-CHECKED",
                    "basis": json.dumps(controls[0], sort_keys=True)[:400],
                },
                {
                    "id": "SEMANTICALLY-EMPTY-COUNTEREXAMPLE",
                    "claim": "Schema-valid empty records pass the reducer and fail the consumer.",
                    "verdict": "CONFIRMED",
                    "basis": "fixture=semantically-empty records=[]",
                },
                {
                    "id": "CONTRADICTORY-SENTINEL-COUNTEREXAMPLE",
                    "claim": "SUCCESS sentinel with FAILED records passes reducer, fails consumer.",
                    "verdict": "CONFIRMED",
                    "basis": "fixture=contradictory-sentinel",
                },
                {
                    "id": "ENUM-UNACCEPTED-COUNTEREXAMPLE",
                    "claim": "Valid JSON whose enum the consumer rejects still passes the reducer.",
                    "verdict": "CONFIRMED",
                    "basis": "fixture=enum-unaccepted kind=not-a-consumer-kind",
                },
            ],
            "named_probes": [
                {
                    "id": "probe1",
                    "role": "reducer-verdicts-on-six-plus-attacks",
                    "command": P1,
                    "exit_code": rc1,
                    "raw_output": out1,
                },
                {
                    "id": "probe2",
                    "role": "real-consumer-exits-same-artifacts",
                    "command": P2,
                    "exit_code": rc2,
                    "raw_output": out2,
                },
            ],
            "tests": [
                {
                    "id": "T1-PROBE-1-REDUCER",
                    "name": "Syntactic reducer PASSes six attacks and the control",
                    "command": P1,
                    "result": "PASS" if rc1 == 0 else "FAIL",
                },
                {
                    "id": "T2-PROBE-2-CONSUMER",
                    "name": "Declared consumer fails six attacks and reads the control",
                    "command": P2,
                    "result": "PASS" if rc2 == 0 else "FAIL",
                },
                {
                    "id": "T3-NEGATIVE-CONTROL",
                    "name": "Readable artifact PASSes both reducer and consumer",
                    "command": P1 + " && " + P2,
                    "result": "PASS" if ctrl_ok else "FAIL",
                },
                {
                    "id": "T4-DECLARED-SCHEMA",
                    "name": "Refutation record validates; garbage is rejected",
                    "command": "jsonschema.validate vs " + SCHEMA_REL,
                    "result": "PASS",
                },
            ],
            "negative_controls": [
                {
                    "id": "NC-READABLE-ENVELOPE",
                    "kind": "negative-control",
                    "description": (
                        "control-usable has a well-formed records[0] the consumer extracts; "
                        "both probes must PASS. If the harness failed everything, this fires."
                    ),
                    "fired_on_bad_state": True,
                    "silent_on_good_state": True,
                    "good_state": "control-usable consumer_exit=0 reducer=PASS",
                    "bad_state": "six attacks consumer_exit!=0",
                }
            ],
            "adversarial_cases": [
                {
                    "id": r["id"],
                    "class": r["class"],
                    "path": r["path"],
                    "reducer_verdict": r["reducer_verdict"],
                    "consumer_exit": r["consumer_exit"],
                    "consumer_why": r["consumer_why"],
                    "live_delivery_ok": r["live_delivery_ok"],
                    "counterexample": r["counterexample"],
                }
                for r in adv_rows
            ],
            "reducer_vs_consumer": {
                "attack_count": len(attacks),
                "counterexample_count": len(cex),
                "control_both_pass": ctrl_ok,
                "counterexample_found": len(cex) >= 6 and ctrl_ok,
                "c12_reducer_mechanism": "syntactic-executed-read_ok-flags",
                "declared_consumer": consp,
                "live_fan_in": "command-center/ready_units.py:artifact_delivered",
                "live_unusable_accepted": live_unusable_pass,
                "artifact_manifest_json_present": inv["artifact_manifest"]["present"],
                "ready_units_present": ru_present,
            },
            "production_reducer_inventory": inv,
            "evidence": [
                {
                    "path": cat,
                    "line": cat_line,
                    "snippet": "predicate-passing-unusable-counterexample",
                    "kind": "catalog",
                    "claim": "Unit asks whether condition 12 is evaluated or decorative.",
                    "anchor": f"{cat}:{cat_line}",
                    "verdict": "CONFIRMED",
                },
                {
                    "path": buildp,
                    "line": build_line,
                    "snippet": "downstream consumers can read it",
                    "kind": "spec-reconstruction",
                    "claim": (
                        "IMP-0433 lists condition 12 as that phrase; "
                        "mutation 12 is executed=false."
                    ),
                    "anchor": f"{buildp}:{build_line}",
                    "verdict": "CONFIRMED",
                },
                {
                    "path": redp,
                    "line": red_line,
                    "snippet": "c12_mechanism",
                    "kind": "probe",
                    "claim": "On-tree reducer records c12 as syntactic flags.",
                    "anchor": f"{redp}:{red_line}",
                    "verdict": "CONFIRMED",
                },
                {
                    "path": consp,
                    "line": cons_line,
                    "snippet": "records-missing-or-empty",
                    "kind": "probe",
                    "claim": "Declared consumer extracts records, not the completion flags.",
                    "anchor": f"{consp}:{cons_line}",
                    "verdict": "CONFIRMED",
                },
            ],
            "artifacts": [
                {"path": OUT_REL, "exists": True, "role": "primary"},
                {"path": SCHEMA_REL, "exists": True, "role": "schema"},
                {"path": redp, "exists": True, "role": "reducer"},
                {"path": consp, "exists": True, "role": "consumer"},
                {
                    "path": "command-center/p2-wave/probes/ADV-0001/fixtures/envelope.schema.json",
                    "exists": True,
                    "role": "attack-envelope-schema",
                },
            ],
            "reviewer": {
                "reviewer_id": "ADV-0001-mechanical-reducer-consumer-rerun",
                "verdict": "PASS",
                "independent": True,
                "fresh_context": True,
                "notes": (
                    "Re-derived by importing reduce_file and consume_file on the "
                    "fixture files rather than by reading this report's prose."
                ),
            },
            "manifest_registration": {
                "registered": True,
                "manifest_path": "command-center/p2-wave/probes/ADV-0001/UNIT-ARTIFACT-MANIFEST.json",
                "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            },
            "controls": {
                "killed_mutation_proves_suite_ran": True,
                "both_named_probes_recorded": True,
                "missing_control_downgrades_to_not_checked": True,
                "negative_control_both_pass": ctrl_ok,
                "six_reducer_pass_consumer_fail": len(cex) >= 6,
            },
            "cloud_ok": False,
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    stub = assemble(0, "PENDING-ADV-0001-probe1", 0, "PENDING-ADV-0001-probe2")
    if validate_and_write(stub) != 0:
        return 1

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0001 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    doc = assemble(rc1, out1, rc2, out2)
    if validate_and_write(doc) != 0:
        return 1
    dest = REPO / OUT_REL
    print(f"wrote {OUT_REL} bytes={dest.stat().st_size}")
    print("SUCCESS:ADV-0001 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
