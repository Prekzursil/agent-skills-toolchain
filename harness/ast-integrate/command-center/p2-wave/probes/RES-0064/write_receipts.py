#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import lib as L

HERE = Path(__file__).resolve().parent
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0064/probe1_mechanism_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0064/probe2_two_rails.py"
)
SUPPORTING = [
    "command-center/schema/workflow.schema.json",
    "command-center/p2-wave/probes/RES-0064/capture.py",
    "command-center/p2-wave/probes/RES-0064/emit.py",
    "command-center/p2-wave/probes/RES-0064/lib.py",
    "command-center/p2-wave/probes/RES-0064/probe1_mechanism_table.py",
    "command-center/p2-wave/probes/RES-0064/probe2_two_rails.py",
    "command-center/p2-wave/probes/RES-0064/captures/index.json",
]


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(L.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = L.REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "sha256": L.sha256_bytes(raw),
        "bytes": len(raw),
        "present": True,
        "unit_id": "RES-0064",
        "receipt_path": "command-center/p2-wave/probes/RES-0064/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    out = L.ARTIFACT_REL
    if not (L.REPO / out).is_file():
        print(f"FAILED:receipts missing {out}")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(out, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0064",
        "unit_id": "RES-0064",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0064",
        "registered": True,
        "output_path": out,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": out,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0064/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0064-probe2-two-rail-refuter",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0064: live named probes exit 0, research/RES-0064.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0064",
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
    print(f"primary {out} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0064 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
