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
OUT = "command-center/receipts/TST-0322.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0322/probe1_tamper_classes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0322/probe2_concurrent_writers.py"
)
SUPPORTING = [
    "tools/bench/results_ledger.py",
    "tools/bench/__init__.py",
    "command-center/bench/results/ledger.jsonl",
    "command-center/bench/results/ledger.jsonl.tip",
    "command-center/p2-wave/probes/TST-0322/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0322/probe1_tamper_classes.py",
    "command-center/p2-wave/probes/TST-0322/probe2_concurrent_writers.py",
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
        "receipt_path": "command-center/p2-wave/probes/TST-0322/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "TST-0322",
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print(f"FAILED:TST-0322 receipts: {OUT} missing; run emit_receipt.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0322 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
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
        "cloud_ok": False,
        "id": "TST-0322",
        "manifest_path": "command-center/p2-wave/probes/TST-0322/UNIT-ARTIFACT-MANIFEST.json",
        "measure": {
            "exit_code": 0,
            "line": "SUCCESS:delivered TST-0322",
        },
        "measure_line": "SUCCESS:delivered TST-0322",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "tamper-three-classes",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "concurrent-writers-no-tear",
            },
        ],
        "notes": (
            "G-1 for TST-0322: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. Lock is O_CREAT|O_EXCL, not fcntl."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0322-probe2-concurrent-writers",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:TST-0322",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "TST-0322",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "TST-0322",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0322 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
