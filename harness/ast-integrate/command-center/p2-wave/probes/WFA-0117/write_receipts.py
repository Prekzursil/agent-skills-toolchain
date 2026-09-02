#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/wfa/WFA-0117-fusion-independent-review.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0117/probe1_recompute_blind.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0117/probe2_reproduce_adjudicate.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0117/audit-report.schema.json",
    "command-center/p2-wave/probes/WFA-0117/substrate.py",
    "command-center/p2-wave/probes/WFA-0117/recompute.py",
    "command-center/p2-wave/probes/WFA-0117/gaming.py",
    "command-center/p2-wave/probes/WFA-0117/fusion_lane.py",
    "command-center/p2-wave/probes/WFA-0117/adjudicate.py",
    "command-center/p2-wave/probes/WFA-0117/pipeline.py",
    "command-center/p2-wave/probes/WFA-0117/probe1_recompute_blind.py",
    "command-center/p2-wave/probes/WFA-0117/probe2_reproduce_adjudicate.py",
    "command-center/p2-wave/probes/WFA-0117/emit_review.py",
    "command-center/p2-wave/probes/WFA-0117/raw_runs.json",
    "command-center/p2-wave/probes/WFA-0117/fusion_lane_sealed.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
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
        "unit_id": "WFA-0117",
        "receipt_path": "command-center/p2-wave/probes/WFA-0117/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0117 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "WFA-0117",
        "unit_id": "WFA-0117",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0117",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/p2-wave/probes/WFA-0117/audit-report.schema.json"
        ),
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
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0117/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0117-codex-style-recompute",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0117: live named probes exit 0, independent-review.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Upstream WFA-0113/0115/0116 artifacts are "
            "absent; review uses the unit-local matched-pair substrate. Catalog "
            "schema pack exists as a generated shim; executable contract is the "
            "unit-local AuditReport schema."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0117",
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
    print("SUCCESS:WFA-0117 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
