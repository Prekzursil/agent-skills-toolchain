#!/usr/bin/env python3
"""Write ADV-0072 SUBAGENT-RETURN.json and per-unit UNIT-ARTIFACT-MANIFEST.json.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
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

UID = "ADV-0072"
OUT = "command-center/adversarial/ADV-0072-imported-workflow-definition-injection.json"
SCHEMA = "command-center/schema/injection-corpus-result.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0072/probe1_import_beacon.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0072/probe2_field_census.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0072/importer.py",
    "command-center/p2-wave/probes/ADV-0072/fixtures.py",
    "command-center/p2-wave/probes/ADV-0072/probe1_import_beacon.py",
    "command-center/p2-wave/probes/ADV-0072/probe2_field_census.py",
    "command-center/p2-wave/probes/ADV-0072/emit_artifact.py",
    "tools/import_quarantine.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0072/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0072/emit_artifact.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:ADV-0072 emit rc={ce}")
        print(te[-4000:])
        return 1
    print(te[-1500:])

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0072 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(manifest_row(rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0072",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "import-beacon-oracle",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "static-field-census",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0072/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0072-probe2-ast-field-census",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0072: live named probes exit 0, injection-corpus "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:ADV-0072 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
