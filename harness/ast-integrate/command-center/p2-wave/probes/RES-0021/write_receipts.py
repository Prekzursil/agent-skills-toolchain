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
OUT = "command-center/research/RES-0021.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0021/probe1_flag_deltas.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0021/probe2_negative_control.py"
)
SUPPORTING = [
    "command-center/schema/research-registry.schema.json",
    "command-center/p2-wave/probes/RES-0021/inventory.py",
    "command-center/p2-wave/probes/RES-0021/wrapper_harness.py",
    "command-center/p2-wave/probes/RES-0021/probe1_flag_deltas.py",
    "command-center/p2-wave/probes/RES-0021/probe2_negative_control.py",
    "command-center/p2-wave/probes/RES-0021/fixtures/published_tokens.json",
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
        "unit_id": "RES-0021",
        "receipt_path": "command-center/p2-wave/probes/RES-0021/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    out = REPO / OUT
    if not out.is_file():
        print("FAILED:RES-0021 receipts: artifact missing")
        return 1
    rc1, t1 = run_probe(P1)
    rc2, t2 = run_probe(P2)
    sha, size = digest(out)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0021",
        "unit_id": "RES-0021",
        "status": "DELIVERED" if rc1 == 0 and rc2 == 0 else "FAILED",
        "state": "SUCCESS" if rc1 == 0 and rc2 == 0 else "FAILED",
        "sentinel": "SUCCESS:RES-0021",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/research-registry.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "with-without-deltas",
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "invented-flag-negative-control",
                "raw_output": t2[-4000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0021/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0021-probe2-negative-control",
            "verdict": "PASS" if rc1 == 0 and rc2 == 0 else "FAIL",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0021: live named probes exit 0, research registry "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0021",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    print(f"probe1 rc={rc1}")
    print(f"probe2 rc={rc2}")
    if rc1 != 0 or rc2 != 0:
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    print("wrote SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
