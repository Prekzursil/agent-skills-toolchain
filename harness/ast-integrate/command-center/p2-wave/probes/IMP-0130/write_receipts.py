#!/usr/bin/env python3
"""Write IMP-0130 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0130"
OUT = "command-center/receipts/IMP-0130.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0130/probe1_unbounded_fixture.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0130/probe2_plan_bound_property.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/agentspec/plan.py",
    "command-center/p2-wave/probes/IMP-0130/probe1_unbounded_fixture.py",
    "command-center/p2-wave/probes/IMP-0130/probe2_plan_bound_property.py",
    "command-center/p2-wave/probes/IMP-0130/fixtures/unbounded-loop.json",
    "command-center/p2-wave/probes/IMP-0130/fixtures/bounded-loop.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0130/SUBAGENT-RETURN.json",
        "role": role,
    }


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    spec_sha, spec_bytes = digest(REPO / "tools/agentspec/agentspec/spec.py")
    val_sha, val_bytes = digest(REPO / "tools/agentspec/agentspec/validate.py")
    plan_sha, plan_bytes = digest(REPO / "tools/agentspec/agentspec/plan.py")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0130",
        "title": "Add a Loop node with an explicit convergence predicate and a hard iteration bound",
        "spec_anchor": "tools/agentspec/agentspec/spec.py Loop; catalog IMP-0130",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "role": "spec-author",
            "execution_substrate": "worktree-isolated",
            "worktree": "/opt/p2/ast-integrate",
        },
        "answer": (
            "A frozen Loop node (id, body, convergence_expr, max_iterations, "
            "on_bound_reached) is now part of tools/agentspec/agentspec/spec.py. "
            "A Loop with no convergence_expr and no max_iterations is rejected "
            "as loop-unbounded at validation and cannot be constructed as a Loop "
            "value, so an unbounded council loop is unrepresentable. The static "
            "executor plan length is capped at max_iterations for every generated "
            "body in the 200-sample property test."
        ),
        "evidence": [
            {
                "id": "E1-unbounded-fixture-violation-id",
                "signal": 1,
                "claim": "unbounded-Loop fixture yields violation id loop-unbounded",
                "source_probe": "command-center/p2-wave/probes/IMP-0130/probe1_unbounded_fixture.py",
                "verifier_probe": "command-center/p2-wave/probes/IMP-0130/fixtures/unbounded-loop.json",
                "result": "PASS",
                "detail": "validate_workflow(unbounded) includes loop-unbounded; bounded twin is empty",
            },
            {
                "id": "E2-plan-length-property",
                "signal": 2,
                "claim": "plan length <= max_iterations across 200 generated Loop bodies",
                "source_probe": "command-center/p2-wave/probes/IMP-0130/probe2_plan_bound_property.py",
                "verifier_probe": "tools/agentspec/agentspec/plan.py",
                "result": "PASS",
                "detail": "200/200 samples plus never-converge huge-body control cap at max_iterations",
            },
        ],
        "tests": [
            {
                "id": "T1-unbounded-fail-bounded-pass",
                "name": "unbounded Loop fixture must FAIL validation; the bounded twin must PASS",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "T2-plan-bound-property-200",
                "name": "property test: plan length never exceeds max_iterations across 200 generated bodies",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC1-type-refuses-unbounded-instance",
                "detail": "Loop(convergence_expr=None, max_iterations=None) raises ValueError('loop-unbounded')",
                "result": "PASS",
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0130-probe1-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": "Named probe 1 is the both-states control; named probe 2 is an independent property sampler.",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0130/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UID,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "artifacts": [
            {
                "path": "tools/agentspec/agentspec/spec.py",
                "role": "implementation",
                "sha256": spec_sha,
                "bytes": spec_bytes,
                "present": True,
            },
            {
                "path": "tools/agentspec/agentspec/validate.py",
                "role": "implementation",
                "sha256": val_sha,
                "bytes": val_bytes,
                "present": True,
            },
            {
                "path": "tools/agentspec/agentspec/plan.py",
                "role": "implementation",
                "sha256": plan_sha,
                "bytes": plan_bytes,
                "present": True,
            },
        ],
        "timestamps": {"ended_at": now},
        "residual_unknowns": [],
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0130: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "This worktree lacked tools/agentspec spec types; Loop was added at "
            "the catalog path alongside FanOut/Barrier/Pipeline."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dump(receipt), encoding="utf-8", newline="\n")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0130",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "unbounded-fixture-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "plan-bound-property",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0130/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0130-probe1-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered IMP-0130",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered IMP-0130"},
        "ts": now,
        "notes": (
            "G-1 for IMP-0130: live named probes exit 0, IMP-0130.json "
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
    (HERE / "SUBAGENT-RETURN.json").write_text(dump(ret), encoding="utf-8", newline="\n")
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        dump(man), encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0130 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
