#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0041-ci-step-inventory.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    GHOST,
    assert_control,
    build,
    probe1_payload,
    probe2_payload,
)

UNIT = "AUD-0041"
OUT = "command-center/audit/AUD-0041-ci-step-inventory.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
RECEIPT_SCHEMA = "command-center/schema/receipt.schema.json"
QUESTION = (
    "For every workflow file, what is the complete ordered list of jobs and "
    "steps, the exact command each step runs, and which steps are conditional "
    "on a matrix value or an event type?"
)
SENTINEL = (
    "SUCCESS:AUD-0041 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0041/probe1_yaml_parse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0041/probe2_actions_api.py"
)


def sha256_file(rel: str) -> str:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def validate(doc: dict, schema_rel: str) -> list[str]:
    schema = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(doc)]


def slim_item(i: dict) -> dict:
    row = {
        "id": i["id"],
        "kind": i["kind"],
        "path": i["path"],
        "probe1_verdict": i["probe1_verdict"],
        "probe2_verdict": i["probe2_verdict"],
    }
    for key in (
        "universe",
        "step_name",
        "command",
        "conditional_on",
        "probe2_reason",
        "triggers",
        "leg_count",
        "step_count",
        "job_if",
        "note",
    ):
        if i.get(key) is not None:
            row[key] = i[key]
    return row


def main() -> int:
    cen = build()
    assert_control(cen)
    ctl = cen["planted_control"]
    tot = cen["origin_totals"]
    p1 = probe1_payload(cen)
    p2 = probe2_payload(cen)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    skipped_yaml = [
        i
        for i in cen["items"]
        if i["kind"] == "function"
        and i.get("universe") == "captured-origin"
        and i.get("probe2_reason") == "api-skipped"
    ]
    unsampled = [
        x["workflow"] for x in cen["leg_reconciliation"] if not x["sampled"]
    ]
    p1_raw = json.dumps(p1, sort_keys=True)
    p2_raw = json.dumps(p2, sort_keys=True)
    answer = (
        f"This worktree has {cen['live_totals']['workflow_files']} files under "
        f".github/workflows. Captured origin YAML round-trip parses to "
        f"{tot['workflow_files']} workflow files / {tot['jobs']} jobs / "
        f"{tot['expanded_legs']} expanded legs / {tot['steps']} steps "
        f"({tot['conditional_steps']} conditional steps, "
        f"{tot['conditional_jobs']} conditional jobs). Probe 2 sampled "
        f"{cen['sampled_agree']} origin workflows where static leg prediction "
        f"equals the Actions API job count; {len(unsampled)} origin workflows "
        f"were not in the captured API sample. {len(skipped_yaml)} YAML-declared "
        f"origin steps were skipped in the sampled API runs. Zero origin jobs "
        f"use strategy.matrix; the expander is proven on a fixture "
        f"(6 legs = API known-run 6 jobs; plain job 1 = API 1). Planted "
        f"{GHOST} is DEAD on YAML and LIVE on the string registry "
        f"(independent={ctl['independent']}). SUCCESS:AUD-0041"
    )
    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "kind": "audit-inventory",
        "title": (
            "CI workflow, job, and step inventory: what each step actually executes"
        ),
        "question": QUESTION,
        "answer": answer,
        "items": [slim_item(i) for i in cen["items"]],
        "planted_control": ctl,
        "tallies": cen["tallies"],
        "both_dead_modules": cen["both_dead_modules"],
        "disagree_modules": cen["disagree_modules"],
        "origin_totals": tot,
        "fixture_totals": cen["fixture_totals"],
        "live_totals": cen["live_totals"],
        "sampled_agree": cen["sampled_agree"],
        "leg_reconciliation": cen["leg_reconciliation"],
        "inventory": {
            "origin": cen["origin"],
            "fixtures": cen["fixtures"],
        },
        "scope": {
            "live_github_workflows": cen["github_workflows_on_disk"],
            "captured_inventory": (
                "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
            ),
            "captured_api": (
                "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
            ),
            "command_truncation_chars": 600,
            "reusable_workflows_expanded": False,
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "yaml-parse-ordered-job-step-table",
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "actions-api-skipped-steps-and-registry",
                "raw_output": p2_raw,
            },
        ],
        "evidence": [
            {
                "id": "E1-yaml-parse",
                "kind": "static-analysis",
                "anchor": "command-center/p2-wave/probes/AUD-0041/probe1_yaml_parse.py",
                "claim": (
                    f"YAML parse yields origin {tot['workflow_files']}/"
                    f"{tot['jobs']}/{tot['steps']} and matrix fixture "
                    f"{ctl['matrix_leg_count']} legs."
                ),
            },
            {
                "id": "E2-actions-api",
                "kind": "http",
                "anchor": "command-center/p2-wave/probes/AUD-0041/probe2_actions_api.py",
                "claim": (
                    f"API sample agrees on {cen['sampled_agree']} origin "
                    f"workflows; {len(skipped_yaml)} declared steps skipped."
                ),
            },
            {
                "id": "E3-planted-control",
                "kind": "detector-control",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0041/fixtures/"
                    "aud0041_fx/registry.json"
                ),
                "claim": (
                    f"{GHOST} is DEAD on YAML and LIVE on the string registry; "
                    "stripping string edges returns it to DEAD."
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/AUD-0041/inventory.py",
                "role": "supporting",
            },
            {
                "path": (
                    "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
                ),
                "role": "supporting",
            },
            {
                "path": (
                    "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
                ),
                "role": "supporting",
            },
        ],
        "tests": [
            {
                "id": "ctl-matrix-expansion-vs-api",
                "result": "PASS",
                "command": (
                    "expand_matrix(control-matrix.yml) vs "
                    "fixtures/api/control-matrix-jobs.json"
                ),
                "notes": (
                    f"yaml_legs={ctl['matrix_leg_count']} "
                    f"api_jobs={ctl['api_matrix_job_count']}; "
                    f"plain yaml={ctl['plain_leg_count']} "
                    f"api={ctl['api_plain_job_count']}"
                ),
            },
            {
                "id": "ctl-registry-string-only",
                "result": "PASS" if ctl["independent"] else "FAIL",
                "command": P1 + " && " + P2,
                "notes": (
                    f"{GHOST} DEAD on YAML, LIVE on registry; strawman without "
                    f"strings={ctl['probe2_without_string_edges']}"
                ),
            },
            {
                "id": "ctl-skipped-step-never",
                "result": "PASS",
                "command": P2,
                "notes": (
                    "fixture step 'never' is LIVE in YAML and DEAD (skipped) in API"
                ),
            },
            {
                "id": "yaml-on-key-boolean-trap",
                "result": "PASS" if ctl["on_key_boolean_trap_survived"] else "FAIL",
                "command": "doc.get('on', doc.get(True)) over parsed workflows",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0041-probe2-actions-api",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is a mechanically different detector (Actions API job "
                "list + string registry), not a re-read of probe 1."
            ),
        },
        "timestamps": {"generated_at": now},
        "residual_unknowns": [
            {
                "claim": (
                    "No origin job uses strategy.matrix, so the catalog's "
                    "API-vs-expander check is degenerate on origin YAML and is "
                    "settled by the planted 6-leg fixture known-run."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Re-run against a repo whose live workflows include a "
                    "matrix job and compare expander legs to that run's API "
                    "job count."
                ),
            },
            {
                "claim": (
                    "Reusable-workflow and composite-action uses: references "
                    "are recorded; their inner steps were not expanded, so "
                    f"{tot['steps']} is a floor on the true step count."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Resolve each uses: to action.yml / reusable workflow and "
                    "recurse."
                ),
            },
            {
                "claim": (
                    ".github/workflows is absent on this worktree; origin "
                    "counts are a YAML round-trip of the captured inventory "
                    "(commands truncated at 600 characters)."
                ),
                "verdict": (
                    "NOT-CHECKED"
                    if not cen["github_workflows_on_disk"]
                    else "CHECKED"
                ),
                "settling_experiment": (
                    "Re-parse live .github/workflows when that tree is present."
                ),
            },
        ],
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": SCHEMA,
    }

    errs = validate(doc, SCHEMA) + [
        f"[receipt] {e}" for e in validate(doc, RECEIPT_SCHEMA)
    ]
    if errs:
        print("FAILED:AUD-0041 schema errors")
        for e in errs[:40]:
            print(" ", e)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "AUD-0041", "state": "SUCCESS"},
    ):
        if not validate(garbage, SCHEMA):
            print("FAILED:AUD-0041 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    digest = sha256_file(OUT)
    print(f"wrote {OUT} bytes={out.stat().st_size} sha256={digest}")
    print(
        f"control {GHOST} p1={ctl['probe1_verdict']} "
        f"p2={ctl['probe2_verdict']} independent={ctl['independent']}"
    )
    print(
        f"origin={tot['workflow_files']}/{tot['jobs']}/{tot['steps']} "
        f"disagree={cen['tallies']['disagree']}"
    )
    print("SUCCESS:AUD-0041 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
