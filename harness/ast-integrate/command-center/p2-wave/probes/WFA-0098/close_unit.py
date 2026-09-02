#!/usr/bin/env python3
"""Emit artifact, run named probes, write per-unit return + manifest."""
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
UNIT = "WFA-0098"
OUT_REL = "command-center/wfa/WFA-0098-duplicate-threshold-calibration.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0098/probe1_labelled_sweep.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0098/probe2_asymmetric_cost.py"
)

SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0098/labelled_pairs.py",
    "command-center/p2-wave/probes/WFA-0098/calibrate.py",
    "command-center/p2-wave/probes/WFA-0098/emit.py",
    "command-center/p2-wave/probes/WFA-0098/probe1_labelled_sweep.py",
    "command-center/p2-wave/probes/WFA-0098/probe2_asymmetric_cost.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
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
    digest, n = sha256_file(path)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": n,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0098/emit.py"
    )
    code, out = run_cmd(emit_cmd)
    print(out)
    if code != 0:
        print("FAILED:WFA-0098-close emit")
        return 1

    c1, t1 = run_cmd(P1)
    print(t1)
    if c1 != 0:
        print("FAILED:WFA-0098-close probe1")
        return 1
    c2, t2 = run_cmd(P2)
    print(t2)
    if c2 != 0:
        print("FAILED:WFA-0098-close probe2")
        return 1

    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(rel, "supporting") for rel in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0098",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SemanticDiff",
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
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0098-probe2-asymmetric-cost",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for WFA-0098: live named probes exit 0, SemanticDiff "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Lexical Jaccard "
            "calibration; WFA-0007/0008/0096 artifacts absent on this tree."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT_REL} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("SUCCESS:WFA-0098-close")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
