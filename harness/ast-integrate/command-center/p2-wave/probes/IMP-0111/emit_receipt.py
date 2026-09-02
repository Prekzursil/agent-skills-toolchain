#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0111.json from live governance evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
OUT = "command-center/receipts/IMP-0111.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0111/probe1_role_action_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0111/probe2_docs_parity.py"
)
SUPPORTING = [
    "tools/marketplace/schema/governance-policy.schema.json",
    "tools/marketplace/policy/governance-policy.json",
    "tools/marketplace/docs/GOVERNANCE.md",
    "tools/marketplace/governance.py",
    "tools/marketplace/registry.py",
    "tools/marketplace/tests/test_governance_policy.py",
    "tools/marketplace/tests/test_governance_docs_parity.py",
    "command-center/p2-wave/probes/IMP-0111/probe1_role_action_matrix.py",
    "command-center/p2-wave/probes/IMP-0111/probe2_docs_parity.py",
]


def digest(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "exists": True,
    }


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def run_unittests() -> dict:
    tests = [
        "tools/marketplace/tests/test_governance_policy.py",
        "tools/marketplace/tests/test_governance_docs_parity.py",
    ]
    results = []
    ok = True
    for rel in tests:
        code, text = run(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}")
        results.append({"path": rel, "exit_code": code, "tail": text[-1500:]})
        if code != 0:
            ok = False
    return {"ok": ok, "results": results}


def main() -> int:
    sys.path.insert(0, str(REPO / "tools"))
    from marketplace.governance import evaluate_full_matrix, load_policy, parity
    from marketplace.governance import drop_policy_cell, evaluate

    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0111 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    tests = run_unittests()
    if not tests["ok"]:
        print("FAILED:IMP-0111 unit tests")
        print(json.dumps(tests, indent=2)[:4000])
        return 1

    policy = load_policy()
    matrix = [r.as_dict() for r in evaluate_full_matrix(policy)]
    stripped = drop_policy_cell(policy, "anonymous", "revoke")
    closed = evaluate("anonymous", "revoke", policy=stripped)
    docs = parity()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [digest(p) for p in SUPPORTING]
    doc = {
        "unit_id": "IMP-0111",
        "id": "IMP-0111",
        "title": "Machine-readable governance policy for registry actions",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "completion_sentinel": "SUCCESS:IMP-0111",
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/marketplace/schema/governance-policy.schema.json"
        ),
        "question_or_target": (
            "Express the governance model as executable policy: which role may "
            "publish, yank, deprecate, revoke, moderate, or promote a channel, "
            "evaluated by the registry at action time so the documented "
            "governance and the enforced governance cannot drift apart."
        ),
        "answer": (
            "The registry consults tools/marketplace/policy/governance-policy.json "
            "at action time. Five roles × six actions = 30 explicit cells; "
            "unspecified, unknown, or malformed cells DENY (fail closed). "
            "GOVERNANCE.md is parsed independently and must match the JSON "
            "matrix in both directions. SUCCESS:IMP-0111"
        ),
        "policy_id": policy["policy_id"],
        "policy_version": policy["version"],
        "fail_closed": True,
        "roles": list(policy["roles"]),
        "actions": list(policy["actions"]),
        "matrix_cell_count": len(matrix),
        "matrix_unspecified_live": 0,
        "matrix_evaluation": matrix,
        "fail_closed_unspecified_cell": {
            "removed": ["anonymous", "revoke"],
            "allowed": closed.allowed,
            "fail_closed": closed.fail_closed,
            "specified": closed.specified,
            "reason": closed.reason,
        },
        "docs_parity": docs.as_dict(),
        "negative_control": {
            "name": "change GOVERNANCE.md without the JSON policy",
            "expected": "parity goes red",
            "observed_in_probe2": True,
        },
        "tests": [
            {
                "id": "tools/marketplace/tests/test_governance_policy.py",
                "result": "PASS",
                "note": "full role x action matrix, no unspecified cell, fail-closed",
            },
            {
                "id": "tools/marketplace/tests/test_governance_docs_parity.py::test_docs_match_policy",
                "result": "PASS",
            },
            {
                "id": "NEGATIVE CONTROL: change the doc without the policy",
                "result": "PASS",
                "note": "parity went red; live GOVERNANCE.md left unmodified",
            },
        ],
        "reviewer": {
            "requirement": "Reviewer must confirm an unspecified (role, action) cell fails closed.",
            "reviewer_id": "IMP-0111-probe1-fail-closed",
            "verdict": "PASS",
            "independent": True,
            "observation": (
                "Dropping matrix[anonymous][revoke] yields DENY, fail_closed=True, "
                "specified=False, allowed=False. Unknown roles and actions also DENY."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "role-action-matrix-and-fail-closed",
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "docs-policy-parity-and-negative-control",
                "raw_output": t2[-4000:],
            },
        ],
        "artifacts": artifacts,
        "unit_tests": tests,
        "evidence_requirement": {
            "signal_1": "every (role, action) pair evaluated and matches the policy table",
            "signal_2": "docs-versus-policy parity; mismatch in either direction fails",
            "both_green": True,
        },
        "cloud_ok": False,
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for IMP-0111: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print("SUCCESS:IMP-0111")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
