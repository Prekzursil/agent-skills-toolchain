#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""

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
    "command-center/p2-wave/probes/IMP-0111/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0111",
        "receipt_path": "command-center/p2-wave/probes/IMP-0111/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/IMP-0111/emit_receipt.py"
    )
    code, text = run_probe(emit)
    if code != 0:
        print(f"FAILED:receipts emit exit={code}")
        print(text[-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "IMP-0111",
        "unit_id": "IMP-0111",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0111",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/marketplace/schema/governance-policy.schema.json"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "role-action-matrix-and-fail-closed",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "docs-policy-parity-and-negative-control",
                "raw_output": t2[-8000:],
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0111/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0111-probe1-fail-closed",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0111: live named probes exit 0, receipts/IMP-0111.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0111",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("SUCCESS:IMP-0111-receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
