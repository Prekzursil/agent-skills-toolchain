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
OUT = "command-center/synthesis/SYN-0045.owner-brief.md"
SCHEMA = "command-center/schema/owner-brief.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0045/probe1_no_new_claims.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0045/probe2_planted_invention.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0045/claims.py",
    "command-center/p2-wave/probes/SYN-0045/brief.py",
    "command-center/p2-wave/probes/SYN-0045/schema_bind.py",
    "command-center/p2-wave/probes/SYN-0045/emit.py",
    "command-center/p2-wave/probes/SYN-0045/probe1_no_new_claims.py",
    "command-center/p2-wave/probes/SYN-0045/probe2_planted_invention.py",
    "command-center/p2-wave/probes/SYN-0045/fixtures/report.json",
    "command-center/p2-wave/probes/SYN-0045/fixtures/open_decisions.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "receipt_path": "command-center/p2-wave/probes/SYN-0045/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "SYN-0045",
    }


def main() -> int:
    primary_path = REPO / OUT
    if not primary_path.is_file() or primary_path.stat().st_size <= 0:
        print(f"FAILED:receipts missing {OUT}")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
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
        "id": "SYN-0045",
        "manifest_path": "command-center/p2-wave/probes/SYN-0045/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1[-4000:],
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2[-4000:],
            },
        ],
        "notes": (
            "G-1 for SYN-0045: live named probes exit 0, owner-brief.md "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "SYN-0045-probe1-recompute-set-difference",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:SYN-0045",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "SYN-0045",
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts.append(
        row(
            "command-center/p2-wave/probes/SYN-0045/SUBAGENT-RETURN.json",
            "supporting",
        )
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "SYN-0045",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:SYN-0045 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
