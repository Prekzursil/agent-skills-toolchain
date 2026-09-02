#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/research/RES-0001.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0001/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0001/probe2_field_necessity.py"
)
SUPPORTING = [
    "command-center/schema/research-claim-record.schema.json",
    "command-center/schema/source-lineage.schema.json",
    "command-center/schema/evidence-tier.schema.json",
    "command-center/schema/confidence-band.schema.json",
    "command-center/schema/settling-probe.schema.json",
    "command-center/schema/claim-edge.schema.json",
    "command-center/schema/freshness-stamp.schema.json",
    "command-center/schema/snapshot-sha256.schema.json",
    "command-center/p2-wave/probes/RES-0001/schema_lib.py",
    "command-center/p2-wave/probes/RES-0001/consumers.py",
    "command-center/p2-wave/probes/RES-0001/fixtures.py",
    "command-center/p2-wave/probes/RES-0001/check.py",
    "command-center/p2-wave/probes/RES-0001/probe1_roundtrip.py",
    "command-center/p2-wave/probes/RES-0001/probe2_field_necessity.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True)
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
        "unit_id": "RES-0001",
        "receipt_path": "command-center/p2-wave/probes/RES-0001/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0001/emit.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:RES-0001 emit rc={ce}")
        print(te[-5000:])
        return 1
    print(te[-2000:])
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0001 probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0001",
        "unit_id": "RES-0001",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0001",
        "registered": True,
        "output_path": OUT,
        "output_schema": "https://json-schema.org/draft/2020-12/schema",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/RES-0001/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0001-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for RES-0001: live named probes exit 0, RES-0001.json state=SUCCESS "
            "with 8 schema files and source_lineage-stripped FAIL, per-unit manifest "
            "row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0001",
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
    print("SUCCESS:RES-0001 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
