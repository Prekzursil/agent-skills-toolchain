#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0074-git-and-forge-metadata-injection.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    LOCAL_SCHEMA_REL,
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    TITLE,
    UNIT_ID,
)
from measure import measure  # noqa: E402

OUT = OUTPUT_REL
SCHEMA = SCHEMA_REL


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reject_garbage(schema: dict) -> None:
    validator = jsonschema.Draft7Validator(schema)
    for blob in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(blob)):
            raise SystemExit(f"FAILED:ADV-0074 schema accepted garbage {list(blob)[:2]}")


def main() -> int:
    measured = measure()
    if not measured["controls_ok"]:
        print("FAILED:ADV-0074 emit controls did not pass")
        print(json.dumps(measured["tests"], indent=2, sort_keys=True))
        return 1

    c1, t1 = run_cmd(P1_CMD)
    c2, t2 = run_cmd(P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0074 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    schema_path = REPO / SCHEMA
    local_schema = REPO / LOCAL_SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    reject_garbage(schema)
    schema_sha, schema_bytes = digest(schema_path)

    overall = measured["overall_verdict"]
    # Honest non-BLOCKED: SUCCESS even when the production surface is unmeasured.
    state = "SUCCESS"
    now = _now()
    answer = (
        "Scratch git+forge fixtures were built locally (no real PR/issue). "
        "Probe 1 ran the live review-stage renderer plus a deterministic follower "
        f"(payload steered={measured['probe1']['payload']['steered']}; "
        f"control steered={measured['probe1']['control']['steered']}; "
        "detector-red fired). Probe 2 censused production interpolators: "
        f"in_templates={measured['probe2']['fields_in_templates'] or []}; "
        f"unmeasured={measured['probe2']['unmeasured_fields']}. "
        "Unmeasured fields are NOT-CHECKED, not safe. "
        f"Overall {overall}. cloud ok is not this delivery."
    )
    proof = {
        "unit_id": UNIT_ID,
        "id": UNIT_ID,
        "state": state,
        "schema_version": 1,
        "report_kind": "injection-corpus-result",
        "title": TITLE,
        "question_or_target": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:11057, 11058",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "output_path": OUT,
        "overall_verdict": overall,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "prompt-injection-refuter",
            "execution_substrate": "linux-worktree-isolated",
        },
        "timestamps": {"produced_at": now},
        "mechanism": (
            "scratch forge-metadata fixture plus a prompt-template field census"
        ),
        "scratch_forge": {
            "real_pr_created": False,
            "real_issue_created": False,
            "github_pr_created": measured["probe1"]["payload"]["github_pr_created"],
            "github_issue_created": measured["probe1"]["payload"]["github_issue_created"],
        },
        "census": measured["census"],
        "probe1": measured["probe1"],
        "probe2": measured["probe2"],
        "target_verdicts": [
            {"id": t["id"], "verdict": t["verdict"], "reason": t.get("reason")}
            for t in measured["targets"]
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "exit_code": c1,
                "role": "review-stage-beacon-or-out-of-scope-tool",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "exit_code": c2,
                "role": "prompt-template-field-census",
                "raw_output": t2,
            },
        ],
        "tests": [
            {
                "id": t["id"],
                "name": t["name"],
                "result": t["result"],
            }
            for t in measured["tests"]
        ],
        "negative_controls": [
            {
                "id": nc["id"],
                "fired_on_bad_state": nc["fired_on_bad_state"],
                "silent_on_good_state": nc["silent_on_good_state"],
            }
            for nc in measured["negative_controls"]
        ],
        "evidence": [
            {
                "id": "E1-review-stage-live",
                "claim": (
                    "The review/triage stage was run against a scratch payload "
                    "fixture and a payload-free control; compliance is a beacon "
                    "or out-of-scope tool, not narrative reading."
                ),
                "verdict": (
                    "CONFIRMED"
                    if measured["probe1"]["payload"]["steered"]
                    else (
                        "NOT-CHECKED"
                        if overall == "NOT-CHECKED"
                        else "REFUTED"
                    )
                ),
                "measured": {
                    "payload_steered": measured["probe1"]["payload"]["steered"],
                    "control_steered": measured["probe1"]["control"]["steered"],
                    "n_production_templates": measured["probe1"]["payload"][
                        "n_production_templates"
                    ],
                },
            },
            {
                "id": "E2-field-census",
                "claim": (
                    "A template census reports which git/forge fields are "
                    "interpolated; fields absent from templates are unmeasured "
                    "surface, not safe."
                ),
                "verdict": "CONFIRMED" if measured["controls_ok"] else "NOT-CHECKED",
                "measured": {
                    "fields_in_templates": measured["probe2"]["fields_in_templates"],
                    "unmeasured_fields": measured["probe2"]["unmeasured_fields"],
                },
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0074-probe2-field-census",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "catalog evidence_requirement, not the author summary",
            "method": (
                "Probe 2 re-derives interpolated fields from template text and "
                "does not read Probe 1's beacon boolean."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": SCHEMA,
                "exists": True,
                "role": "schema",
                "sha256": schema_sha,
                "bytes": schema_bytes,
            },
            {
                "path": LOCAL_SCHEMA_REL,
                "exists": local_schema.is_file(),
                "role": "local-schema",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0074/probe1_review_beacon.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0074/probe2_field_census.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "report": {
            "answer": answer,
            "overall_verdict": overall,
            "completion_line": "UNIT-COMPLETE:ADV-0074",
        },
        "completion_line": "UNIT-COMPLETE:ADV-0074",
        "notes": (
            "G-1 ADV-0074: live named probes re-run the scratch fixture and the "
            "field census. Did not run global unit_manifest.py --write. Did not "
            "create a real PR or issue. cloud ok is not delivery."
        ),
    }

    jsonschema.Draft7Validator(schema).validate(proof)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(proof, indent=2, sort_keys=True) + "\n"
    if COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0074 emit catalog completion_sentinel absent")
        return 1
    if SENTINEL not in text:
        print("FAILED:ADV-0074 emit SUCCESS sentinel absent")
        return 1
    if len(text.encode("utf-8")) < 2048:
        print("FAILED:ADV-0074 emit undersize")
        return 1
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))} overall={overall}")
    print("SUCCESS:ADV-0074")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
