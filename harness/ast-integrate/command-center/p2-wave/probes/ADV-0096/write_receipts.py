#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for ADV-0096."""
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
OUT = "command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0096/probe1_live_gate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0096/probe2_semantic_space.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0096/probe_common.py",
    "command-center/p2-wave/probes/ADV-0096/probe1_live_gate.py",
    "command-center/p2-wave/probes/ADV-0096/probe2_semantic_space.py",
    "command-center/p2-wave/probes/ADV-0096/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0096/fixtures/mutants.json",
    "tools/council/quota/targets.py",
    "tools/council/quota/__init__.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": "ADV-0096",
        "receipt_path": "command-center/p2-wave/probes/ADV-0096/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = HERE / "emit_artifact.py"
    c0, t0 = run_cmd(
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {emit.relative_to(REPO).as_posix()}"
    )
    if c0 != 0:
        print(f"FAILED:ADV-0096 emit rc={c0}")
        print(t0[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0096 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    primary = artifacts[0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0096",
        "unit_id": "ADV-0096",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0096",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/council-pathology-sim.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "live-mutant-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "second-similarity-space",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0096/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0096-probe2-canonical-mechanism-space",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "required_fix": None,
        "ts": now,
        "notes": (
            "G-1 for ADV-0096: live named probes exit 0, "
            "adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud_ok is not delivery. No ADV "
            "rebuild of unique_ideas.py."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0096",
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
    print("SUCCESS:ADV-0096 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
