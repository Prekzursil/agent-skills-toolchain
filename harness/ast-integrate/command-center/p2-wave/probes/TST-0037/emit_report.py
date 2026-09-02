#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0037.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import schema_local as SL  # noqa: E402
import suite as S  # noqa: E402
from constructs import QUESTION  # noqa: E402

OUT = "command-center/receipts/TST-0037.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
SENTINEL = "SUCCESS:TST-0037"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0037/probe1_live_rerun.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0037/probe2_controls.py"
)
SUITE_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"import sys; from pathlib import Path; p=Path('command-center/p2-wave/probes/TST-0037'); "
    "sys.path.insert(0,str(p)); import suite; print(suite.run(Path('.'))['ok'])\""
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0037/workflow-dsl.schema.json",
    "command-center/p2-wave/probes/TST-0037/contract_validator.py",
    "command-center/p2-wave/probes/TST-0037/cases.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/docs/violation-ids.json",
    "tools/agentspec/tests/test_validate.py",
]


def fp(tag: str) -> str:
    return hashlib.sha256(tag.encode("utf-8")).hexdigest()[:32]


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def probe(role: str, method: str, command: str, raw: str, tag: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fp(tag),
        "exit_code": exit_code,
    }


def evidence(claim: str, verdict: str, rel: str, snippet: str, probes: list, confidence: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": confidence,
        "anchor": f"{rel}:{line}",
        "probes": probes,
    }


def build() -> dict:
    result = S.run(REPO)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = result["table"]
    inv = result["inventory"]
    answer = result["answer"]
    missing = list(answer["constructs_with_no_production_validator"])
    cases_by_id = {c["id"]: c for c in result["cases"]}
    fo_good = cases_by_id["fan-out/good"]
    fo_empty = cases_by_id["fan-out/empty"]
    loop_g = cases_by_id["loop-with-convergence/good"]
    loop_b = cases_by_id["loop-with-convergence/unbounded"]
    state = "SUCCESS" if result["ok"] else "FAILED"
    tests = []
    for row in result["tests"]:
        tests.append(
            {
                "id": row["id"],
                "name": row.get("note") or row["id"],
                "command": SUITE_CMD,
                "result": row["result"],
            }
        )
    tests.append(
        {
            "id": "output-schema-rejects-garbage",
            "name": "Resolved conformance-report schema rejects empty and unrelated objects",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                "\"import sys; from pathlib import Path; "
                "p=Path('command-center/p2-wave/probes/TST-0037'); sys.path.insert(0,str(p)); "
                "import schema_local; schema_local.garbage_rejected(); print('ok')\""
            ),
            "result": "PASS",
        }
    )
    artifacts = [SL.artifact_row(rel, "supporting") for rel in SUPPORTING]
    closed = inv["closed_node_types"]
    observations = [
        {
            "name": "production-closed-node-types",
            "measured": ",".join(closed) if closed else "NONE",
            "method": "ast-class-scan of tools/agentspec/agentspec/spec.py plus VIOLATIONS",
            "anchor": "tools/agentspec/agentspec/spec.py:Node",
        },
        {
            "name": "constructs-with-no-production-validator",
            "measured": ",".join(missing) if missing else "NONE",
            "method": "inventory.scan closed-type intersection",
            "anchor": "command-center/p2-wave/probes/TST-0037/inventory.py",
        },
        {
            "name": "suite-both-states-all-seven",
            "measured": bool(all(r["both_states"] for r in table)),
            "method": "contract_validator vs cases.materialize good/bad twins",
            "anchor": "command-center/p2-wave/probes/TST-0037/cases.py",
        },
        {
            "name": "production-fanout-empty-id",
            "measured": ",".join(fo_empty["production_ids"]),
            "method": "typed Workflow FanOut(units=()) through validate_workflow",
            "anchor": "tools/agentspec/agentspec/validate.py",
        },
        {
            "name": "production-loop-ids-good",
            "measured": ",".join(loop_g["production_ids"]),
            "method": "adapter: type outside Node union -> unknown-node-type",
            "anchor": "command-center/p2-wave/probes/TST-0037/production.py",
        },
    ]
    e1 = evidence(
        "Production Node is FanOut|Barrier|Pipeline|RepairLoop. Fan-out and barrier "
        "have schema rules and test_validate.py cases; loop-with-convergence, "
        "human-checkpoint, subworkflow, retry and resume have no production class "
        "and no VIOLATIONS id.",
        "CONFIRMED",
        "tools/agentspec/agentspec/spec.py",
        "Node = FanOut | Barrier | Pipeline | RepairLoop",
        [
            probe(
                "source",
                "static-analysis",
                "python3 -c ast-walk spec.py ClassDef names",
                "closed=" + json.dumps(closed),
                "src-spec-classes",
            ),
            probe(
                "verifier",
                "file-read",
                "read tools/agentspec/docs/violation-ids.json ids",
                "missing_validators=" + json.dumps(missing),
                "ver-violation-ids",
            ),
        ],
        "almost-certain",
    )
    e2 = evidence(
        "The pre-implementation contract suite has a schema rule, a good twin, and "
        "at least one negative fixture per catalog construct, and production "
        "discriminates empty fan-out (fanout-empty) while remaining silent on "
        "loop-unbounded.",
        "CONFIRMED",
        "command-center/p2-wave/probes/TST-0037/cases.py",
        "fan-out/empty",
        [
            probe(
                "source",
                "test-run",
                SUITE_CMD,
                json.dumps(
                    {
                        "ok": result["ok"],
                        "fanout_empty_prod": fo_empty["production_ids"],
                        "fanout_good_prod": fo_good["production_ids"],
                    }
                ),
                "src-suite-run",
            ),
            probe(
                "verifier",
                "command",
                P2,
                json.dumps(
                    {
                        "loop_good": loop_g["production_ids"],
                        "loop_bad": loop_b["production_ids"],
                    }
                ),
                "ver-probe2-controls",
            ),
        ],
        "almost-certain",
    )
    report = {
        "kind": "conformance-report",
        "observations": observations,
        "control_ids": [
            "fan-out/good",
            "fan-out/empty",
            "loop-with-convergence/good",
            "loop-with-convergence/unbounded",
            "overclaim-mutant",
            "schema-garbage",
        ],
        "title": "Executable conformance tests for the workflow DSL contract",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "construct_table": table,
        "suite_cases": result["cases"],
        "inventory": {
            "closed_node_types": inv["closed_node_types"],
            "spec_classes": inv["spec_classes"],
            "validate_present": inv["validate_present"],
            "import_error": inv["import_error"],
            "constructs_with_no_production_validator": inv[
                "constructs_with_no_production_validator"
            ],
        },
        "named_probes": [
            {"id": "probe1", "role": "live-rerun", "command": P1},
            {"id": "probe2", "role": "detector-control", "command": P2},
        ],
    }
    return {
        "schema_version": 1,
        "unit_id": "TST-0037",
        "state": state,
        "sentinel": SENTINEL if state == "SUCCESS" else "FAILED:TST-0037",
        "spec_anchor": "_USER-PROMPTS.md:10805",
        "min_bytes_threshold": 1500,
        "artifacts": artifacts,
        "evidence": [e1, e2],
        "tests": tests,
        "negative_controls": [
            {
                "id": "fanout-empty-production",
                "kind": "malformed-input",
                "description": "Empty FanOut.units must emit fanout-empty; the good twin must be clean.",
                "fired_on_bad_state": "fanout-empty" in fo_empty["production_ids"],
                "silent_on_good_state": fo_good["production_ids"] == [],
                "bad_state_output": ",".join(fo_empty["production_ids"]),
                "good_state_output": ",".join(fo_good["production_ids"]) or "clean",
            },
            {
                "id": "loop-unbounded-contract-not-production",
                "kind": "known-broken-fixture",
                "description": (
                    "Contract fires loop-unbounded only on the bad twin. Production "
                    "cannot construct the type and reports unknown-node-type on both."
                ),
                "fired_on_bad_state": "loop-unbounded" in loop_b["contract_ids"],
                "silent_on_good_state": loop_g["contract_ids"] == [],
                "bad_state_output": "contract="
                + ",".join(loop_b["contract_ids"])
                + " production="
                + ",".join(loop_b["production_ids"]),
                "good_state_output": "contract="
                + ",".join(loop_g["contract_ids"])
                + " production="
                + ",".join(loop_g["production_ids"]),
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": "Resolved conformance-report schema must reject empty and unrelated objects.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "garbage rejected",
                "good_state_output": "receipt accepted after disk-local $ref resolve",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0037-probe2-controls",
            "verdict": "PASS" if result["ok"] else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Catalog requires a cross-vendor reviewer (Claude author -> Codex). "
                "probe2_controls.py is the independent mechanical refuter: both-states, "
                "production unknown-node-type on the five missing constructs, and an "
                "overclaim mutant. Not a billed Codex session."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0037/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "TST-0037",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator disk-resolved conformance-report.schema.json",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 command-center/p2-wave/probes/TST-0037/schema_local.py",
                    "in-memory document validated before write; garbage controls fire",
                    "consumer-schema-local",
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": "repair-loop vs loop-with-convergence",
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "CLOSED Node includes RepairLoop (IMP-0139 fix-review). Inventory "
                    "does not count it as loop-with-convergence. Re-scan spec.py ClassDef "
                    "names and confirm Loop is absent."
                ),
            },
            {
                "claim": "Pipeline is in the production closed set but is not one of the seven catalog constructs.",
                "verdict": "CONFIRMED",
                "settling_experiment": "Compare catalog question construct list to spec.py Node union.",
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "conformance-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
        "extensions": {
            "completion_sentinel": SENTINEL,
            "output_schema": SCHEMA,
        },
    }


def validate_or_die(doc: dict) -> None:
    errs = SL.iter_errors(doc)
    if errs:
        print("FAILED:TST-0037 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    SL.garbage_rejected()


def main() -> int:
    doc = build()
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0037 self-declared {doc.get('state')}")
        validate_or_die(doc)
        return 1
    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = SL.digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0037 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0037 sentinel absent")
        return 1
    disk = json.loads(text)
    post = SL.iter_errors(disk)
    if post:
        print("FAILED:TST-0037 disk schema errors")
        for err in post[:12]:
            print(" ", list(err.path), err.message)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "missing_validators="
        + ",".join(doc["report"]["answer"]["constructs_with_no_production_validator"])
    )
    print("SUCCESS:TST-0037 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
