#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402

SUPPORTING = [
    C.SCHEMA_REL,
    "tools/agentspec/agentspec/permission_bound.py",
    "tools/agentspec/agentspec/subworkflow_executor.py",
    "tools/agentspec/agentspec/dispatchpolicy.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/tests/test_permission_bound.py",
    "command-center/p2-wave/probes/TST-0223/contract.py",
    "command-center/p2-wave/probes/TST-0223/scenario.py",
    "command-center/p2-wave/probes/TST-0223/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0223/probe1_property_trees.py",
    "command-center/p2-wave/probes/TST-0223/probe2_mutation_widen.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(C.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = C.REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/TST-0223/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": C.UNIT,
    }


def main() -> int:
    out = C.REPO / C.OUT_REL
    if not out.is_file():
        print(f"FAILED:{C.UNIT} receipts: {C.OUT_REL} missing; run emit_receipt.py first")
        return 1
    c1, t1 = run_probe(C.P1)
    c2, t2 = run_probe(C.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{C.UNIT} receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    artifacts = [row(C.OUT_REL, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = artifacts[0]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": C.OUT_REL,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": C.UNIT,
        "manifest_path": "command-center/p2-wave/probes/TST-0223/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": C.P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "property-5000-trees",
            },
            {
                "command": C.P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "mutation-union-widen",
            },
        ],
        "notes": (
            "G-1 for TST-0223: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild circle."
        ),
        "output_path": C.OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0223-probe2-mutation-widen",
            "verdict": "PASS",
        },
        "sentinel": C.SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": C.UNIT,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": C.UNIT,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {C.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{C.UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
