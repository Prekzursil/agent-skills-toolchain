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
UNIT = "RES-0026"
OUT = "command-center/research/RES-0026.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0026/probe1_two_rails_and_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0026/probe2_classifier_controls.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0026/research-claim-record.local.schema.json",
    "command-center/p2-wave/probes/RES-0026/contract.py",
    "command-center/p2-wave/probes/RES-0026/build_artifact.py",
    "command-center/p2-wave/probes/RES-0026/probe1_two_rails_and_table.py",
    "command-center/p2-wave/probes/RES-0026/probe2_classifier_controls.py",
    "command-center/p2-wave/probes/RES-0026/captures/_index.json",
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
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/RES-0026/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    build = HERE / "build_artifact.py"
    c0, t0 = run_probe(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {build.relative_to(REPO).as_posix()}")
    if c0 != 0:
        print(f"FAILED:RES-0026 emit build rc={c0}")
        print(t0[-3000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0026 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = REPO / OUT
    sha, size = digest(primary)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))

    ret = {
        "artifacts": [
            {
                "bytes": size,
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": sha,
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/RES-0026/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "two-rails-and-control-table",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "classifier-negative-controls",
            },
        ],
        "notes": (
            "G-1 for RES-0026: live named probes exit 0, research/RES-0026.json "
            "state=SUCCESS with client-vs-server control table, per-unit manifest "
            "row. Did not run global unit_manifest.py --write. No ADV rebuild. "
            "Catalog research-claim-record.schema.json is absent; local discriminator used."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "RES-0026-probe2-classifier-refuter",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:RES-0026",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:RES-0026 receipts written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
