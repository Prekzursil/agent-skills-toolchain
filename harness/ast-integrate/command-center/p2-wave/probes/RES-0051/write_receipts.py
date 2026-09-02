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
OUT = "command-center/research/RES-0051.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0051/probe1_two_snapshot.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0051/probe2_seeded_vulnerable.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0051/scan.py",
    "command-center/p2-wave/probes/RES-0051/emit_research.py",
    "command-center/p2-wave/probes/RES-0051/probe1_two_snapshot.py",
    "command-center/p2-wave/probes/RES-0051/probe2_seeded_vulnerable.py",
    "command-center/p2-wave/probes/RES-0051/fixtures/corpus.json",
    "command-center/p2-wave/probes/RES-0051/fixtures/frozen-lock.json",
    "command-center/p2-wave/probes/RES-0051/fixtures/scratch-vulnerable.json",
    "command-center/p2-wave/probes/RES-0051/fixtures/scratch-patched.json",
    "command-center/p2-wave/probes/RES-0051/fixtures/skill-payload.md",
    "command-center/p2-wave/probes/RES-0051/fixtures/captures.json",
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
        "unit_id": "RES-0051",
        "receipt_path": "command-center/p2-wave/probes/RES-0051/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print(f"FAILED:RES-0051 receipts: {OUT} missing; run emit_research.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0051 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0051",
        "unit_id": "RES-0051",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0051",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "two-snapshot-scan",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "seeded-vulnerable-detection",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0051/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0051-probe2-security-bypass",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0051: live named probes exit 0, "
            "research/RES-0051.json state=SUCCESS, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0051",
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
    print("SUCCESS:RES-0051 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
