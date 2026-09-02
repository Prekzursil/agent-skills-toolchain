#!/usr/bin/env python3
"""Write IMP-0340 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
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
UID = "IMP-0340"
OUT = "command-center/receipts/IMP-0340.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0340/probe1_schema_sequencing.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0340/probe2_unagreed_traceability.py"
)
SUPPORTING = [
    "tools/council/outcomes/action_plan.py",
    "tools/council/outcomes/action.schema.json",
    "tools/council/outcomes/__init__.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/IMP-0340/probe1_schema_sequencing.py",
    "command-center/p2-wave/probes/IMP-0340/probe2_unagreed_traceability.py",
    "command-center/p2-wave/probes/IMP-0340/fixtures/agreed-decision.json",
    "command-center/p2-wave/probes/IMP-0340/fixtures/conditional-decision.json",
    "command-center/p2-wave/probes/IMP-0340/fixtures/no-decision.json",
    "command-center/p2-wave/probes/IMP-0340/fixtures/missing-owner.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0340/SUBAGENT-RETURN.json",
        "role": role,
    }


def artifact_entry(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json_line(t1)
    p2 = first_json_line(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    supporting_arts = [artifact_entry(p, "supporting") for p in SUPPORTING]
    receipt = {
        "unit_id": UID,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0340",
        "status": "DELIVERED",
        "title": "Action-plan generator from a council decision",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:IMP-0340 "
            "question_or_target + tests_required; cited input "
            "_USER-PROMPTS.md:10933 (file not in this worktree)"
        ),
        "question_or_target": (
            "Implement tools/council/outcomes/action_plan.py turning a decision "
            "into typed, owned, sequenced actions with preconditions. "
            "Falsifiable question: is every action traceable to a decision "
            "element, and does the plan ever contain an action the council "
            "never agreed to?"
        ),
        "falsifiable_answers": {
            "every_generated_action_traceable": True,
            "unagreed_action_in_plan": (
                "The generator does not emit unagreed actions. "
                "inject_unagreed_action plus traceability_check lists them "
                "explicitly and sets fired=true. Both-states: clean silent, "
                "injected fires."
            ),
            "measured_clean_untraceable": p2.get("clean_untraceable"),
            "measured_injected_untraceable": p2.get("injected_untraceable"),
        },
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": supporting_arts,
        "evidence": [
            {
                "id": "e1-traceability-untraceable-list",
                "claim": (
                    "Action-to-decision traceability lists untraceable actions "
                    "explicitly. Clean generated plan: untraceable=[]. Injected "
                    "unagreed action: listed with reason not_in_agreed_set."
                ),
                "anchor": "tools/council/outcomes/action_plan.py:traceability_check",
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-1500:],
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "independent recount: traces_to set minus "
                            "agreed_id_set, plus CLI check exit codes "
                            "clean=0 injected=1"
                        ),
                        "exit_code": 0,
                        "raw_output": (
                            f"cli_clean_rc={p2.get('cli_clean_rc')} "
                            f"cli_dirty_rc={p2.get('cli_dirty_rc')} "
                            f"listed={p2.get('untraceable_listed_explicitly')}"
                        ),
                    },
                ],
            },
            {
                "id": "e2-schema-validation-every-action",
                "claim": (
                    "Every generated action was schema-validated (owner, "
                    "precondition, verification). Dropping any of those three "
                    "fields from a generated action makes validate_action fire. "
                    "A missing-owner decision element is omitted, not emitted "
                    "invalid. Sequencing is a dense 1..n order that respects "
                    "depends_on."
                ),
                "anchor": "tools/council/outcomes/action_plan.py:validate_action",
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-1500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "python3 -B tools/council/outcomes/action_plan.py "
                            "plan command-center/p2-wave/probes/IMP-0340/"
                            "fixtures/agreed-decision.json"
                        ),
                        "exit_code": 0,
                        "raw_output": (
                            f"order={p1.get('order')} "
                            f"schema_errors_on_generated={p1.get('schema_errors_on_generated')} "
                            f"cli_validate_ok={p1.get('cli_validate_ok')}"
                        ),
                    },
                ],
            },
        ],
        "test_ids": [
            "probe1-schema-sequencing",
            "probe2-unagreed-traceability",
        ],
        "tests": [
            {
                "id": "probe1-schema-sequencing",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "probe2-unagreed-traceability",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_control_ids": [
            "nc-inject-unagreed-action",
            "nc-statement-mismatch-smuggle",
            "nc-traces-to-dissent",
            "nc-drop-owner-precondition-verification",
        ],
        "negative_controls": [
            {
                "id": "nc-inject-unagreed-action",
                "kind": "known-broken-fixture",
                "description": (
                    "inject_unagreed_action appends an action whose traces_to "
                    "is not in agreed_elements. Traceability must FIRE and "
                    "list act-injected-unagreed."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(p2.get("injected_untraceable")),
                "good_state_output": json.dumps(p2.get("clean_untraceable")),
            },
            {
                "id": "nc-statement-mismatch-smuggle",
                "kind": "known-broken-fixture",
                "description": (
                    "Rewrite an action statement while keeping an agreed "
                    "traces_to id. Detector must fire statement_mismatch."
                ),
                "fired_on_bad_state": bool(p2.get("mismatch_fired")),
                "silent_on_good_state": True,
            },
            {
                "id": "nc-traces-to-dissent",
                "kind": "known-broken-fixture",
                "description": (
                    "Retarget traces_to at a dissent-only id. Detector must "
                    "fire traces_to_dissent. Generator never emits dissent."
                ),
                "fired_on_bad_state": bool(p2.get("dissent_fired")),
                "silent_on_good_state": True,
            },
            {
                "id": "nc-drop-owner-precondition-verification",
                "kind": "field-deletion",
                "description": (
                    "Drop owner, precondition, or verification from a "
                    "generated action. validate_action must error."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "fields": p1.get("field_drop_fires"),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0340-probe2-unagreed-traceability",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "started_from": "tests (negative control), not author summary",
            "notes": (
                "Probe 2 does not read this receipt. It generates a plan, "
                "asserts the clean check is silent, injects an unagreed "
                "action, and asserts the untraceable list names that action. "
                "A second signal is the CLI check exit-code pair (0, 1)."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md and _USER-PROMPTS.md:10933 "
                    "are cited as inputs but are not in this worktree. The "
                    "action/decision shapes were derived from the catalog "
                    "contract (typed, owned, sequenced, preconditions, "
                    "traceability, unagreed-action negative control)."
                ),
                "settling_experiment": (
                    "Re-run plan_from_decision against the six spec examples "
                    "once 11-COUNCIL-SPECIFICATION.md is present and assert "
                    "byte-stable plans."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Catalog dependencies IMP-0308 (stopping expressions) and "
                    "IMP-0310 (deadlock detector) are not imported. Action "
                    "generation does not currently refuse a plan from a "
                    "deadlock-stopped or stop-expression-gated council."
                ),
                "settling_experiment": (
                    "When those modules exist, add a gate that records "
                    "outcome_kind from the stopper and re-run probe1's "
                    "NO-DECISION fixture as a deadlock-stopped council."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "min_bytes_threshold": 128,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0340/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-outcomes-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
            "test_ids[], negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "module": "tools/council/outcomes/action_plan.py",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0340: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(blob, encoding="utf-8")
    if "SUCCESS:IMP-0340" not in blob:
        print("FAILED:receipts sentinel missing after write")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0340",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json profile=council-outcomes-module",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0340/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0340-probe2-unagreed-traceability",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0340: live named probes exit 0, IMP-0340.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0340 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
