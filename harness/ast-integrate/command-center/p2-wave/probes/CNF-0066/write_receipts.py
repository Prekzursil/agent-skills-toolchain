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
OUT = "command-center/confirmation/CNF-0066-negative-result-recheck.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0066/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0066/probe2_independence.py"
)
SUPPORTING = [
    "command-center/schema/detector-control.schema.json",
    "command-center/p2-wave/probes/CNF-0066/engine.py",
    "command-center/p2-wave/probes/CNF-0066/contract.py",
    "command-center/p2-wave/probes/CNF-0066/emit.py",
    "command-center/p2-wave/probes/CNF-0066/probe1_controls.py",
    "command-center/p2-wave/probes/CNF-0066/probe2_independence.py",
    "command-center/p2-wave/probes/CNF-0066/fixtures/known_present/CONTROL.txt",
    "command-center/p2-wave/probes/CNF-0066/fixtures/false_absence/present.txt",
    "command-center/p2-wave/probes/CNF-0066/fixtures/wrong_path/hidden/item.txt",
    "command-center/p2-wave/probes/CNF-0066/fixtures/wrong_field/doc.json",
    "command-center/p2-wave/probes/CNF-0066/fixtures/stale/index.json",
    "command-center/p2-wave/probes/CNF-0066/fixtures/recall_vault/notes/Program-B-note.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/CNF-0066/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "CNF-0066",
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0066/emit.py"
    )
    code, text = run_probe(emit)
    if code != 0:
        print(f"FAILED:receipts emit rc={code}")
        print(text[-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
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
        "id": "CNF-0066",
        "manifest_path": "command-center/p2-wave/probes/CNF-0066/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "control-pairing",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "independence-and-recall",
            },
        ],
        "notes": (
            "G-1 for CNF-0066: live named probes exit 0, negative-result recheck "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/detector-control.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CNF-0066-probe2-independence",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CNF-0066",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "CNF-0066",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "CNF-0066",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNF-0066 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
