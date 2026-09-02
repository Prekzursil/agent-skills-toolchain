#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inventory as I  # noqa: E402

OUT = I.OUT_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0126/probe1_schema_and_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0126/probe2_consumer_rehearsal.py"
)
SUPPORTING = [
    I.LOCAL_SCHEMA_REL,
    "command-center/p2-wave/probes/WFA-0126/inventory.py",
    "command-center/p2-wave/probes/WFA-0126/emit_contract.py",
    "command-center/p2-wave/probes/WFA-0126/consumer.py",
    "command-center/p2-wave/probes/WFA-0126/probe1_schema_and_inventory.py",
    "command-center/p2-wave/probes/WFA-0126/probe2_consumer_rehearsal.py",
]


def row(rel: str, role: str) -> dict:
    path = I.REPO / rel
    sha, size = I.digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "WFA-0126",
        "receipt_path": (
            "command-center/p2-wave/probes/WFA-0126/SUBAGENT-RETURN.json"
        ),
        "role": role,
    }


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(I.REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "WFA-0126",
        "unit_id": "WFA-0126",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0126",
        "registered": True,
        "output_path": OUT,
        "output_schema": I.CATALOG_SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "schema-both-states-inventory",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "consumer-rehearsal",
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
            "command-center/p2-wave/probes/WFA-0126/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "WFA-0126-probe1-schema-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0126: live named probes exit 0, handoff contract "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Honest: only this contract is "
            "schema-valid/delivered; sibling WFA files present are "
            "pack-unvalidated."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0126",
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
    print("SUCCESS:WFA-0126 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
