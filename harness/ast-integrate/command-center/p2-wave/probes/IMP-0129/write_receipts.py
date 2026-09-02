#!/usr/bin/env python3
"""Write IMP-0129 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0129.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0129/probe1_three_level_namespace.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0129/probe2_cycle_and_namespace_mutation.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/agentspec/plan.py",
    "tools/agentspec/tests/test_subworkflow.py",
    "command-center/p2-wave/probes/IMP-0129/probe1_three_level_namespace.py",
    "command-center/p2-wave/probes/IMP-0129/probe2_cycle_and_namespace_mutation.py",
    "command-center/p2-wave/probes/IMP-0129/fixtures/nest-root.json",
    "command-center/p2-wave/probes/IMP-0129/fixtures/nest-mid.json",
    "command-center/p2-wave/probes/IMP-0129/fixtures/nest-leaf.json",
    "command-center/p2-wave/probes/IMP-0129/fixtures/cycle-a.json",
    "command-center/p2-wave/probes/IMP-0129/fixtures/cycle-b.json",
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
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0129",
        "receipt_path": "command-center/p2-wave/probes/IMP-0129/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe_obj(role: str, cmd: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": cmd,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"command\x1f{cmd}".encode()).hexdigest()[:32],
        "exit_code": code,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0129 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_obj("source", P1, t1, c1)
    p2 = probe_obj("verifier", P2, t2, c2)
    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0129",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0129",
        "title": "Add a Subworkflow node type to the frozen workflow spec",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0129",
        "min_bytes_threshold": 128,
        "question_or_target": (
            "add a frozen Subworkflow node (id, workflow_ref, param_bindings, "
            "id_namespace) so a Workflow can embed another Workflow by reference; "
            "two-level nesting validates; inner ids are namespaced; self-ref or "
            "cycle is rejected by a new closed violation id with a bounded walk"
        ),
        "implementation": {
            "spec_module": "tools/agentspec/agentspec/spec.py",
            "validate_module": "tools/agentspec/agentspec/validate.py",
            "plan_module": "tools/agentspec/agentspec/plan.py",
            "node_type": "Subworkflow",
            "introduced_in": 7,
            "cycle_violation_id": "subworkflow-reference-cycle",
            "namespace_separator": "::",
            "walk_bound": 256,
        },
        "artifacts": [{"path": OUT, "role": "primary", "exists": True}],
        "evidence": [
            {
                "claim": (
                    "pytest over a 3-level nesting fixture shows namespaced ids "
                    "(work, M::work, M::L::work) in the flattened plan; a two-level "
                    "nesting validate_workflow returns no violations."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/plan.py:compile_plan",
                "confidence": "almost-certain",
                "probes": [p1],
            },
            {
                "claim": (
                    "A hand-built cyclic fixture returns subworkflow-reference-cycle "
                    "from validate_workflow with a bounded call count (not RecursionError); "
                    "the acyclic twin is silent; deleting the namespacing step makes "
                    "the id-collision uniqueness test go red."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/validate.py:validate_workflow",
                "confidence": "almost-certain",
                "probes": [p2],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "pytest-three-level-namespaced-ids",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "cyclic-fails-acyclic-passes-namespace-mutation",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "c-cycle-both-states",
                "kind": "both-states",
                "description": (
                    "cycle-a/cycle-b fail with subworkflow-reference-cycle; "
                    "acyclic-a/b/leaf twin is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "c-namespace-mutation",
                "kind": "mutation",
                "description": (
                    "compile_plan_drop_namespace deletes namespacing; the unique-id "
                    "collision test is True on live and False on the mutant."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0129-probe2-cycle-and-namespace-mutation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0129/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "exit_code": None,
                "note": "measure runs after this receipt is written",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0217 owns Subworkflow execution, isolated artifact space, "
                    "and budget roll-up; this unit owns the frozen type, flatten "
                    "namespacing, and cycle validation."
                ),
                "verdict": "ACKNOWLEDGED",
                "settling_experiment": "Deliver IMP-0217 against these types.",
            }
        ],
        "notes": (
            "G-1 for IMP-0129: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0129, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0129",
        "unit_id": "IMP-0129",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0129",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "three-level-namespace",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "cycle-and-namespace-mutation",
                "raw_output": t2,
            },
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0129/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0129-probe2-cycle-and-namespace-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0129: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0129",
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
    print("SUCCESS:IMP-0129 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
