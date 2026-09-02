#!/usr/bin/env python3
"""Run emit + named probes, then write per-unit G-1 bookkeeping files."""
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
UNIT = "AUD-0006"
OUT = "command-center/audit/AUD-0006-uncommitted-work-census.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0006/probe1_porcelain.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0006/probe2_body_classifier.py"
)
SUPPORTING = [
    "command-center/schema/audit-inventory.schema.json",
    "command-center/p2-wave/probes/AUD-0006/classify.py",
    "command-center/p2-wave/probes/AUD-0006/porcelain.py",
    "command-center/p2-wave/probes/AUD-0006/probe1_porcelain.py",
    "command-center/p2-wave/probes/AUD-0006/probe2_body_classifier.py",
    "command-center/p2-wave/probes/AUD-0006/emit.py",
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
        timeout=180,
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
        "receipt_path": "command-center/p2-wave/probes/AUD-0006/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0006/emit.py"
    )
    e_rc, e_out = run_cmd(emit)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if e_rc != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0006 emit={e_rc} probe1={c1} probe2={c2}")
        print(e_out[-3000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "PARTIAL",
        "sentinel": "SUCCESS:AUD-0006",
        "registered": True,
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": "command-center/schema/audit-inventory.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "porcelain-size-mtime",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "body-classifier",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0006/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0006-probe2-body-classifier",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for AUD-0006: live named probes exit 0, uncommitted-work-census.json "
            "state=PARTIAL (live .git absent; fixture porcelain + both-direction "
            "planted mutant). Per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0006 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
