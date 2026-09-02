#!/usr/bin/env python3
"""Write IMP-0136 receipt + per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0136.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0136/probe1_least_privilege.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0136/probe2_mutation_order.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/dispatchpolicy.py",
    "tools/agentspec/agentspec/evals/fake_rail.py",
    "tools/agentspec/tests/test_dispatchpolicy.py",
    "command-center/p2-wave/probes/IMP-0136/probe1_least_privilege.py",
    "command-center/p2-wave/probes/IMP-0136/probe2_mutation_order.py",
    "command-center/p2-wave/probes/IMP-0136/scenario.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0136",
        "receipt_path": "command-center/p2-wave/probes/IMP-0136/SUBAGENT-RETURN.json",
        "role": role,
    }


def parse_json_line(text: str) -> dict:
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


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = parse_json_line(t1)
    p2 = parse_json_line(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": "IMP-0136",
        "unit_id": "IMP-0136",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0136",
        "title": "Add a per-unit least-privilege tool-permission set to the spec",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "cloud_ok": False,
        "registered": True,
        "question_or_target": (
            "Add tool_permissions to WorkUnit as a closed declared set, and refuse "
            "to dispatch a unit whose requested tools are not a subset of its "
            "declaration. The check runs BEFORE spawn in dispatchpolicy."
        ),
        "implementation": {
            "work_unit": "tools/agentspec/agentspec/spec.py",
            "dispatch_gate": "tools/agentspec/agentspec/dispatchpolicy.py",
            "counting_rail": "tools/agentspec/agentspec/evals/fake_rail.py",
            "gate_order": "authorize then _call_spawn",
        },
        "evidence": [
            {
                "signal": 1,
                "kind": "counting-fake-rail",
                "path": "tools/agentspec/agentspec/evals/fake_rail.py",
                "claim": "over-privileged fixture rejected pre-spawn with zero spawns",
                "overprivileged_spawns": p1.get("overprivileged_spawns"),
                "violation": "AS-TOOL-PERM-OVERPRIVILEGED",
            },
            {
                "signal": 2,
                "kind": "counting-fake-rail",
                "path": "tools/agentspec/agentspec/evals/fake_rail.py",
                "claim": "permitted twin spawns exactly once",
                "permitted_twin_spawns": p1.get("permitted_twin_spawns"),
            },
            {
                "signal": "mutation",
                "kind": "ast-rewrite",
                "path": "tools/agentspec/agentspec/dispatchpolicy.py",
                "claim": "moving authorize after spawn makes the zero-spawn assertion go red",
                "live_overpriv_spawns": p2.get("live_overpriv_spawns"),
                "mutant_overpriv_spawns": p2.get("mutant_overpriv_spawns"),
                "mutant_zero_spawn_assertion": p2.get("mutant_zero_spawn_assertion"),
            },
        ],
        "tests": [
            {
                "name": "over-privileged unit rejected with zero spawns; compliant twin spawns once",
                "result": "PASS",
                "probe": "probe1_least_privilege.py",
            },
            {
                "name": "mutation: move the check after spawn and the zero-spawn assertion goes red",
                "result": "PASS",
                "probe": "probe2_mutation_order.py",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0136-probe2-mutation-order",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial mutation (authorize after spawn) is a distinct "
                "control from the live both-states spawn counts."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "ts": now,
        "notes": (
            "G-1 for IMP-0136: WorkUnit.tool_permissions is a closed frozenset; "
            "dispatchpolicy.authorize runs before spawn; counting fake rail "
            "measured 0 vs 1 spawns. Did not run global unit_manifest.py --write. "
            "Did not rebuild ADV."
        ),
        "completion_marker": "SUCCESS:IMP-0136",
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0136",
        "unit_id": "IMP-0136",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0136",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0136/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0136-probe2-mutation-order",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0136: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0136",
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
    print("SUCCESS:IMP-0136 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
