#!/usr/bin/env python3
"""Emit RES-0080 research record, re-run named probes, write per-unit G-1 files."""
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

import emit as E  # noqa: E402

UNIT = "RES-0080"
OUT = E.OUT
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0080/probe1_detector_fields.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0080/probe2_not_portable.py"
)
SUPPORTING = [
    "tools/council/kernel.py",
    "tools/council/antifail/unanimity.py",
    "tools/council/topology/chair.py",
    "command-center/schema/council-audit.schema.json",
    "command-center/p2-wave/probes/RES-0080/fields.py",
    "command-center/p2-wave/probes/RES-0080/detectors.py",
    "command-center/p2-wave/probes/RES-0080/fixtures.py",
    "command-center/p2-wave/probes/RES-0080/emit.py",
    "command-center/p2-wave/probes/RES-0080/probe1_detector_fields.py",
    "command-center/p2-wave/probes/RES-0080/probe2_not_portable.py",
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/RES-0080/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc = E.main()
    if rc != 0:
        return rc

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0080 emit probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": E.CATALOG_SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "detector-fields-exist",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "not-portable-control",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0080/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0080-probe2-adversarial-refuter",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0080: live named probes exit 0, research record "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
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
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("SUCCESS:RES-0080 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
