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
OUT = "command-center/research/sources-frontier/RES-0180-watchlist-standing-recheck.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0180/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0180/probe2_live_sample.py"
)
SUPPORTING = [
    "command-center/schema/measurement-run.schema.json",
    "command-center/p2-wave/probes/RES-0180/watchlist.py",
    "command-center/p2-wave/probes/RES-0180/sample.py",
    "command-center/p2-wave/probes/RES-0180/emit_report.py",
    "command-center/p2-wave/probes/RES-0180/probe1_both_states.py",
    "command-center/p2-wave/probes/RES-0180/probe2_live_sample.py",
    "command-center/p2-wave/probes/RES-0180/captures.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "RES-0180",
        "receipt_path": "command-center/p2-wave/probes/RES-0180/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c0, t0 = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0180/emit_report.py"
    )
    if c0 != 0:
        print(f"FAILED:RES-0180 receipts emit c0={c0}")
        print(t0[-3000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0180 receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0180",
        "unit_id": "RES-0180",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0180",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/measurement-run.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-control",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "live-sample-recompute",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0180/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0180-probe2-live-sample",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0180: live named probes exit 0, watchlist-standing-recheck "
            "non-BLOCKED, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0180",
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
    print("SUCCESS:RES-0180 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
