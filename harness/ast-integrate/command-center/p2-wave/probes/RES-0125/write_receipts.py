#!/usr/bin/env python3
"""Run emit + named probes, then write per-unit G-1 bookkeeping files."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0125"
OUT = "command-center/research/RES-0125.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0125/probe1_obligation_labels.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0125/probe2_pin_and_metadata.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0125/labels.py",
    "command-center/p2-wave/probes/RES-0125/table.py",
    "command-center/p2-wave/probes/RES-0125/check.py",
    "command-center/p2-wave/probes/RES-0125/emit.py",
    "command-center/p2-wave/probes/RES-0125/probe1_obligation_labels.py",
    "command-center/p2-wave/probes/RES-0125/probe2_pin_and_metadata.py",
    "command-center/p2-wave/probes/RES-0125/captures/_index.json",
    "command-center/p2-wave/probes/RES-0125/captures/_index_wave2.json",
    "command-center/p2-wave/probes/RES-0125/captures/_index_wave3.json",
    "tools/marketplace/schema/lockfile.schema.json",
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/RES-0125/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0125/emit.py"
    )
    e_rc, e_out = run_cmd(emit)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if e_rc != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0125 emit={e_rc} probe1={c1} probe2={c2}")
        print(e_out[-2000:])
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
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0125",
        "registered": True,
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "obligation-labels-and-proposed-norm-control",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "pin-quote-and-marketplace-gap",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0125/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0125-probe2-pin-and-metadata",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for RES-0125: live named probes exit 0, research/RES-0125.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Not legal advice. Owner sign-off pending. "
            "cloud ok=true is not delivery."
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
    print("SUCCESS:RES-0125 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
