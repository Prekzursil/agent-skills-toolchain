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
OUT = "command-center/wfa/WFA-0073-disposition-evidence-gate.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0073/probe1_current_state.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0073/probe2_both_states.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0073/gate.py",
    "command-center/p2-wave/probes/WFA-0073/registry.py",
    "command-center/p2-wave/probes/WFA-0073/controls.py",
    "command-center/p2-wave/probes/WFA-0073/probe1_current_state.py",
    "command-center/p2-wave/probes/WFA-0073/probe2_both_states.py",
    "command-center/p2-wave/probes/WFA-0073/emit.py",
    "command-center/p2-wave/probes/WFA-0073/fixtures/ci-good.json",
    "command-center/p2-wave/probes/WFA-0073/fixtures/ci-bad.json",
    "command-center/p2-wave/probes/WFA-0073/fixtures/smoke-pass.json",
    "command-center/p2-wave/probes/WFA-0073/fixtures/preserved-payload.txt",
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
        timeout=180,
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
        "unit_id": "WFA-0073",
        "receipt_path": "command-center/p2-wave/probes/WFA-0073/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "WFA-0073",
        "unit_id": "WFA-0073",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0073",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture",
        "cloud_ok": False,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "current-state-census",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "both-states-and-ci-default",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0073/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0073-probe2-both-states-and-default-invocation",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0073: live named probes exit 0, disposition-evidence-gate "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Live 284-row registry absent; census used "
            "catalog-histogram stand-in with empty typed evidence (fail-closed)."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0073",
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
    print("SUCCESS:WFA-0073 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
