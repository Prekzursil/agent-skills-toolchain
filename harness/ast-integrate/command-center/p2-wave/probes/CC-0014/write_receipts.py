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
REPO = HERE.parents[3]
OUT = "command-center/receipts/CC-0014.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0014/probe1_status_machine.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0014/probe2_aggregation.py"
)
SUPPORTING = [
    "command-center/schema/test-registry-entry.schema.json",
    "command-center/TEST-REGISTRY.json",
    "command-center/CLAIM-REGISTRY.json",
    "command-center/test_registry_bind.py",
    "command-center/p2-wave/probes/CC-0014/mutate.py",
    "command-center/p2-wave/probes/CC-0014/emit_receipt.py",
    "command-center/p2-wave/probes/CC-0014/probe1_status_machine.py",
    "command-center/p2-wave/probes/CC-0014/probe2_aggregation.py",
    "command-center/p2-wave/probes/CC-0014/fixtures/subject.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": "CC-0014",
        "receipt_path": "command-center/p2-wave/probes/CC-0014/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ecode, etext = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CC-0014/emit_receipt.py"
    )
    if ecode != 0:
        print(f"FAILED:receipts emit rc={ecode}")
        print(etext[-2000:])
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
        "id": "CC-0014",
        "unit_id": "CC-0014",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0014",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-registry-entry.schema.json",
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
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CC-0014/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CC-0014-probe2-independent-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CC-0014: live named probes exit 0, receipts/CC-0014.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CC-0014",
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
    print("SUCCESS:CC-0014 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
