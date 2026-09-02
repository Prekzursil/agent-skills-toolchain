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
import constants as K  # noqa: E402

SUPPORTING = [
    K.SCHEMA_REL,
    "command-center/p2-wave/probes/BLD-0042/census.py",
    "command-center/p2-wave/probes/BLD-0042/constants.py",
    "command-center/p2-wave/probes/BLD-0042/emit_receipt.py",
    "command-center/p2-wave/probes/BLD-0042/validate_schema.py",
    "command-center/p2-wave/probes/BLD-0042/probe1_controls.py",
    "command-center/p2-wave/probes/BLD-0042/probe2_reviewer.py",
    "command-center/p2-wave/probes/BLD-0042/fixtures/planted_defaults.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": K.UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/BLD-0042/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / K.OUT_REL).is_file():
        print("FAILED:receipts primary artifact missing; run emit_receipt.py first")
        return 1
    c1, t1 = run_probe(K.P1)
    c2, t2 = run_probe(K.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(K.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": K.UNIT_ID,
        "unit_id": K.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": K.SENTINEL,
        "registered": True,
        "output_path": K.OUT_REL,
        "output_schema": K.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": K.P1,
                "exit_code": c1,
                "role": "default-exercise-controls-and-ci-join",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": K.P2,
                "exit_code": c2,
                "role": "independent-reviewer-default-mutation",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": K.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/BLD-0042/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "BLD-0042-probe2-independent-default-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for BLD-0042: live named probes exit 0, receipts/BLD-0042.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": K.UNIT_ID,
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
    print(f"primary {K.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:BLD-0042 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
