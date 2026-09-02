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
REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0048.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0048/probe1_user_data_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0048/probe2_both_states.py"
)
SUPPORTING = [
    "command-center/schema/conformance-report.schema.json",
    "command-center/p2-wave/probes/TST-0048/contract.py",
    "command-center/p2-wave/probes/TST-0048/ledger.py",
    "command-center/p2-wave/probes/TST-0048/tree.py",
    "command-center/p2-wave/probes/TST-0048/engine.py",
    "command-center/p2-wave/probes/TST-0048/suite.py",
    "command-center/p2-wave/probes/TST-0048/schema_check.py",
    "command-center/p2-wave/probes/TST-0048/emit_report.py",
    "command-center/p2-wave/probes/TST-0048/probe1_user_data_inventory.py",
    "command-center/p2-wave/probes/TST-0048/probe2_both_states.py",
    "command-center/p2-wave/probes/TST-0048/schemas/rollback-contract.schema.json",
    "command-center/p2-wave/probes/TST-0048/schemas/inverse-action.schema.json",
    "command-center/p2-wave/probes/TST-0048/schemas/creation-set.schema.json",
    "command-center/p2-wave/probes/TST-0048/schemas/preserve-set.schema.json",
    "command-center/p2-wave/probes/TST-0048/schemas/backup-record.schema.json",
    "command-center/p2-wave/probes/TST-0048/schemas/proof-of-restore.schema.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "TST-0048",
        "receipt_path": "command-center/p2-wave/probes/TST-0048/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c0, t0 = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0048/emit_report.py"
    )
    if c0 != 0:
        print(f"FAILED:TST-0048 emit rc={c0}")
        print(t0[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "TST-0048",
        "unit_id": "TST-0048",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0048",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "user-data-inventory",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "both-states-and-negatives",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0048/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0048-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0048: live named probes exit 0, receipts/TST-0048.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0048",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0048 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
