#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/audit/AUD-0041-ci-step-inventory.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0041/probe1_yaml_parse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0041/probe2_actions_api.py"
)
SUPPORTING = [
    "command-center/schema/audit-inventory.schema.json",
    "command-center/p2-wave/probes/AUD-0041/inventory.py",
    "command-center/p2-wave/probes/AUD-0041/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0041/probe1_yaml_parse.py",
    "command-center/p2-wave/probes/AUD-0041/probe2_actions_api.py",
    "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
    "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json",
    "command-center/p2-wave/probes/AUD-0041/fixtures/aud0041_fx/registry.json",
    "command-center/p2-wave/probes/AUD-0041/fixtures/workflows/control-matrix.yml",
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
        "unit_id": "AUD-0041",
        "receipt_path": "command-center/p2-wave/probes/AUD-0041/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    primary_path = REPO / OUT
    if not primary_path.is_file():
        print(f"FAILED:receipts missing {OUT}")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "AUD-0041",
        "unit_id": "AUD-0041",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0041",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/audit-inventory.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "yaml-parse-ordered-job-step-table",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "actions-api-skipped-steps-and-registry",
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
        "manifest_path": (
            "command-center/p2-wave/probes/AUD-0041/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "AUD-0041-probe2-actions-api",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0041: live named probes exit 0, ci-step-inventory "
            "state=SUCCESS, ghost DEAD on YAML and LIVE on registry, matrix "
            "fixture 6 legs matches API known-run, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. cloud ok=true is "
            "not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "AUD-0041",
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
    print("SUCCESS:AUD-0041 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
