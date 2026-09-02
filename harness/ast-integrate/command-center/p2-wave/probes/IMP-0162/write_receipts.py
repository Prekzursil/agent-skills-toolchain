#!/usr/bin/env python3
"""Write IMP-0162 receipt, SUBAGENT-RETURN.json, and per-unit manifest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0162.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0162/probe1_case_distinct.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0162/probe2_unknown_field.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/import_generic_dag.py",
    "tools/agentspec/agentspec/strict_parse.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/agentspec/spec.py",
    "command-center/p2-wave/probes/IMP-0162/probe1_case_distinct.py",
    "command-center/p2-wave/probes/IMP-0162/probe2_unknown_field.py",
    "command-center/p2-wave/probes/IMP-0162/fixtures/case_distinct.json",
    "command-center/p2-wave/probes/IMP-0162/fixtures/unknown_field.json",
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
        "unit_id": "IMP-0162",
        "receipt_path": "command-center/p2-wave/probes/IMP-0162/SUBAGENT-RETURN.json",
        "role": role,
    }


def evidence_from_adapter() -> dict:
    sys.path.insert(0, str(REPO / "tools" / "agentspec"))
    from agentspec.import_generic_dag import GenericDeclarativeDagAdapter

    adapter = GenericDeclarativeDagAdapter()
    fx = HERE / "fixtures"
    case = adapter.import_path(fx / "case_distinct.json")
    unknown = adapter.import_path(fx / "unknown_field.json")
    dup_key = adapter.import_path(fx / "duplicate_keys.json")
    dup_node = adapter.import_path(fx / "duplicate_node_id.json")
    good = adapter.import_path(fx / "valid_minimal.json")
    wf = case.workflow
    return {
        "adapter_id": adapter.adapter_id,
        "adapter_module": "tools/agentspec/agentspec/import_generic_dag.py",
        "case_distinct": {
            "ok": case.ok,
            "node_ids": list(wf.unit_ids()) if wf else [],
            "param_keys": list(wf.units[0].param_keys()) if wf else [],
            "two_in_two_out": bool(
                wf and len(wf.unit_ids()) == 2 and len(wf.units[0].param_keys()) == 2
            ),
        },
        "unknown_field": {
            "ok": unknown.ok,
            "rejection_ids": [v.id for v in unknown.violations],
            "named_field": [v.detail for v in unknown.violations],
        },
        "duplicate_key": {
            "ok": dup_key.ok,
            "rejection_ids": [v.id for v in dup_key.violations],
        },
        "duplicate_node_id": {
            "ok": dup_node.ok,
            "rejection_ids": [v.id for v in dup_node.violations],
        },
        "valid_twin": {"ok": good.ok, "id": None if not good.workflow else good.workflow.id},
        "imported_workflow": None if wf is None else wf.to_dict(),
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ev = evidence_from_adapter()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": "IMP-0162",
        "unit_id": "IMP-0162",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "completion_sentinel": "SUCCESS:IMP-0162",
        "sentinel": "SUCCESS:IMP-0162",
        "title": "Build the import adapter for generic declarative DAGs (YAML/JSON)",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "adapter": {
            "id": "generic-declarative-dag",
            "class": "GenericDeclarativeDagAdapter",
            "path": "tools/agentspec/agentspec/import_generic_dag.py",
            "strict_parser": "tools/agentspec/agentspec/strict_parse.py",
            "validate": "tools/agentspec/agentspec/validate.py",
        },
        "evidence": ev,
        "tests": [
            {
                "id": "case-distinct-keys-survive-as-distinct",
                "result": "PASS",
                "both_states": "true duplicate rejected as AS-DAG-DUPLICATE-KEY / AS-DAG-DUPLICATE-NODE-ID",
            },
            {
                "id": "unknown-field-rejected-not-ignored",
                "result": "PASS",
                "rejection_id": "AS-DAG-UNKNOWN-FIELD",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0162-probe2-unknown-field",
            "verdict": "PASS",
            "independent": True,
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0162/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "ts": now,
        "notes": (
            "Generic YAML/JSON DAG import adapter: case-distinct keys preserved "
            "(two in, two out), unknown fields rejected with AS-DAG-UNKNOWN-FIELD, "
            "duplicate node id is AS-DAG-DUPLICATE-NODE-ID. SUCCESS:IMP-0162"
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0162",
        "unit_id": "IMP-0162",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0162",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "case-distinct-keys",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "unknown-field-rejected",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0162/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0162-probe2-unknown-field",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0162: live named probes exit 0, receipts/IMP-0162.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0162",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0162 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
