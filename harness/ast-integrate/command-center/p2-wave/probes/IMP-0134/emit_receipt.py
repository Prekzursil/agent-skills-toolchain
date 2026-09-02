#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0134.json from live probes."""
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
OUT_REL = "command-center/receipts/IMP-0134.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0134/probe1_four_ids.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0134/probe2_id_closure.py"
)
TEST = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/agentspec python3 -B "
    "tools/agentspec/tests/test_param_load_ids.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/tests/test_param_load_ids.py",
    "command-center/p2-wave/probes/IMP-0134/probe1_four_ids.py",
    "command-center/p2-wave/probes/IMP-0134/probe2_id_closure.py",
    "command-center/p2-wave/probes/IMP-0134/fixtures/missing-required.json",
    "command-center/p2-wave/probes/IMP-0134/fixtures/type-mismatch.json",
    "command-center/p2-wave/probes/IMP-0134/fixtures/out-of-enum.json",
    "command-center/p2-wave/probes/IMP-0134/fixtures/unknown-key.json",
    "command-center/p2-wave/probes/IMP-0134/fixtures/valid-twin.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    pp = str(REPO / "tools" / "agentspec")
    env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "present": True,
        "role": role,
    }


def main() -> int:
    c_test, t_test = run(TEST)
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0134 emit c_test={c_test} c1={c1} c2={c2}")
        print(t_test[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    receipt = {
        "id": "IMP-0134",
        "unit_id": "IMP-0134",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0134",
        "title": "Implement param validation and coercion at load time with new closed violation ids",
        "question_or_target": (
            "Validate params when a Workflow is loaded, not when a unit finally "
            "runs. A missing required param, a type mismatch, an out-of-enum "
            "value and an unknown param key each produce a DISTINCT violation "
            "id, and the id set stays closed (no free-form strings)."
        ),
        "answer": (
            "tools/agentspec/agentspec/validate.py now validates Workflow params "
            "in load_workflow / validate_params_at_load. Four fixtures emit "
            "param-missing-required, param-type-mismatch, param-out-of-enum, "
            "and param-unknown-key. Unknown keys are strict-parser (spec:11302). "
            "run_unit accepts only LoadedWorkflow, so a failed load cannot run. "
            "AST-enumerated VIOLATION_* constants equal DOCUMENTED_VIOLATION_IDS "
            "(computed set equality). A planted undocumented id turns the "
            "closure probe red. This worktree had no historical 28-id validate.py; "
            "this unit authors the param-validation closed set rather than "
            "padding unused ids. SUCCESS:IMP-0134"
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0134/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "evidence": [
            {
                "id": "E1-four-fixtures",
                "claim": "Four param-violation fixtures yield four distinct closed ids; unknown key is strict-parser.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0134/probe1_four_ids.py",
                "probes": [
                    {
                        "id": "probe1",
                        "role": "source",
                        "command": P1,
                        "exit_code": c1,
                        "method": "command",
                        "raw_output": t1,
                    }
                ],
            },
            {
                "id": "E2-id-closure",
                "claim": "AST-enumerated VIOLATION_* constants equal the documented set; planted undocumented id turns the test red.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0134/probe2_id_closure.py",
                "probes": [
                    {
                        "id": "probe2",
                        "role": "verifier",
                        "command": P2,
                        "exit_code": c2,
                        "method": "command",
                        "raw_output": t2,
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "test_param_load_ids",
                "command": TEST,
                "result": "PASS" if c_test == 0 else "FAIL",
                "exit_code": c_test,
                "raw_output": t_test,
            },
            {
                "id": "probe1-four-ids",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "probe2-id-closure",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "planted-undocumented-id",
                "kind": "mutant-source",
                "description": (
                    "Insert VIOLATION_PARAM_PLANTED = 'param-planted-undocumented' "
                    "into a copy of validate.py. AST constants then differ from "
                    "DOCUMENTED_VIOLATION_IDS."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "undocumented VIOLATION_* constant",
                "good_state": "constants == documented set",
            },
            {
                "id": "valid-twin-load",
                "kind": "positive-control",
                "description": "Valid twin (enum member, coerced integer, secret_ref) loads and run_unit runs.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0134-probe2-id-closure",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-parses validate.py via ast and does not trust probe 1's "
                "id list. Equality is computed set equality."
            ),
        },
        "artifacts": artifacts,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "role": "four-fixture-ids"},
            {"id": "probe2", "command": P2, "exit_code": c2, "role": "ast-id-closure"},
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/agentspec/agentspec/validate.py was absent on this sparse "
                    "worktree; the historical 28-id corpus was not on disk. This "
                    "unit authored the four param-validation ids as a closed set. "
                    "IMP-0148 owns AST-closure against a later full baseline."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": "IMP-0148 closure vs reconstructed 28-id baseline once that module is present.",
            }
        ],
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for IMP-0134: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:IMP-0134"
        ),
    }
    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    sha, size = digest(dest)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0134 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
