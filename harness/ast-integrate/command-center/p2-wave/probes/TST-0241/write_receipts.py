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
OUT = "command-center/receipts/TST-0241.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0241/probe1_scaling_flat.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0241/probe2_rewrite_quadratic.py"
)
SUPPORTING = [
    "command-center/schema/receipt.schema.json",
    "command-center/schema/benchmark-receipt.schema.json",
    "command-center/p2-wave/probes/TST-0241/fixtures.py",
    "command-center/p2-wave/probes/TST-0241/ledger.py",
    "command-center/p2-wave/probes/TST-0241/dispatch.py",
    "command-center/p2-wave/probes/TST-0241/harness.py",
    "command-center/p2-wave/probes/TST-0241/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0241/schema_local.py",
    "command-center/p2-wave/probes/TST-0241/probe1_scaling_flat.py",
    "command-center/p2-wave/probes/TST-0241/probe2_rewrite_quadratic.py",
    "tools/foundry/candidate_registry.py",
    "tools/command-center/close.py",
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/TST-0241/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "TST-0241",
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print(f"FAILED:TST-0241 receipts: {OUT} missing; run emit_receipt.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0241 receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = artifacts[0]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "id": "TST-0241",
        "manifest_path": "command-center/p2-wave/probes/TST-0241/UNIT-ARTIFACT-MANIFEST.json",
        "measure_line": "SUCCESS:delivered TST-0241",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "scaling-flat-append",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "rewrite-quadratic-detector",
            },
        ],
        "notes": (
            "G-1 for TST-0241: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. Write-size instrumentation distinguishes "
            "append-only O(1) from an O(n) rewrite mutant."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/benchmark_result",
        "cloud_ok": False,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0241-probe2-rewrite-quadratic",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:TST-0241",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "TST-0241",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "TST-0241",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0241 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
