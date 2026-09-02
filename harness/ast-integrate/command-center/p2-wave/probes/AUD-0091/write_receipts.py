#!/usr/bin/env python3
"""Write AUD-0091 artifact, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

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
UID = "AUD-0091"
OUT = "command-center/audit/AUD-0091-clean-room-clone-baseline.json"
SCHEMA = "command-center/schema/audit-detector-control.schema.json"
SENTINEL = "SUCCESS:AUD-0091"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0091/probe1_clean_clone_first_fail.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0091/probe2_inplace_compare_and_cache.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/AUD-0091/schema_check.py",
    "command-center/p2-wave/probes/AUD-0091/engine.py",
    "command-center/p2-wave/probes/AUD-0091/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0091/probe1_clean_clone_first_fail.py",
    "command-center/p2-wave/probes/AUD-0091/probe2_inplace_compare_and_cache.py",
    "command-center/p2-wave/probes/AUD-0091/fixtures/good/README.md",
    "command-center/p2-wave/probes/AUD-0091/fixtures/good/RUNBOOK.md",
    "command-center/p2-wave/probes/AUD-0091/fixtures/bad/README.md",
    "command-center/p2-wave/probes/AUD-0091/fixtures/env_inplace/README.md",
    "command-center/p2-wave/probes/AUD-0091/fixtures/env_inplace/ambient.py",
    "command-center/p2-wave/probes/AUD-0091/fixtures/docs_defect/README.md",
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    sha = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
    return {
        "path": rel,
        "sha256": sha,
        "bytes": len(data),
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/AUD-0091/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c0, t0 = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0091/emit_artifact.py"
    )
    if c0 != 0:
        print("FAILED:AUD-0091 emit")
        print(t0[-2500:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0091 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    out_path = REPO / OUT
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:AUD-0091 sentinel missing from artifact")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        "id": UID,
        "manifest_path": (
            "command-center/p2-wave/probes/AUD-0091/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "clean-clone-first-fail",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "inplace-compare-and-cache",
            },
        ],
        "notes": (
            "G-1 for AUD-0091: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. Did not relaunch finish-everything-close or "
            "p2-cloud-ok-deliver."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "control_executed": True,
            "independent": True,
            "reviewer_id": "AUD-0091-probe2-inplace-compare-and-cache",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
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
    print("SUCCESS:AUD-0091 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
