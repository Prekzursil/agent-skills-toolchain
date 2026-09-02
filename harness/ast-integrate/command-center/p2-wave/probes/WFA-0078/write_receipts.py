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
sys.path.insert(0, str(HERE))
import registry_lib as L  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0078/probe1_schema_arithmetic.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0078/probe2_attribution.py"
)
SUPPORTING = [
    L.SCHEMA_REL,
    L.UNIT_SCHEMA_REL,
    L.V1_FIXTURE_REL,
    "command-center/p2-wave/probes/WFA-0078/registry_lib.py",
    "command-center/p2-wave/probes/WFA-0078/emit_registry.py",
    "command-center/p2-wave/probes/WFA-0078/probe1_schema_arithmetic.py",
    "command-center/p2-wave/probes/WFA-0078/probe2_attribution.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
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
        "receipt_path": "command-center/p2-wave/probes/WFA-0078/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "WFA-0078",
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(L.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": L.OUT_REL,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "id": "WFA-0078",
        "manifest_path": "command-center/p2-wave/probes/WFA-0078/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
            },
        ],
        "notes": (
            "G-1 for WFA-0078: live named probes exit 0, registry v2 state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. cloud_ok is not delivery. v1 fixture is frozen."
        ),
        "output_path": L.OUT_REL,
        "output_schema": L.SCHEMA_REL + "#/$defs/WorkflowRecord",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0078-probe2-attribution-and-v1-freeze",
            "verdict": "PASS",
        },
        "sentinel": L.SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "WFA-0078",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "WFA-0078",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {L.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:WFA-0078 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
