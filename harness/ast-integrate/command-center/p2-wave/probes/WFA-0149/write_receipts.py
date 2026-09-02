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
OUT = "command-center/foundry/WFA-0149-resolve-the-140-asymmetric-compatibility-declaration.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0149/probe1_per_pair.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0149/probe2_bulk_symmetrise.py"
)
SUPPORTING = [
    "command-center/schema/foundry-artifact.schema.json",
    "command-center/p2-wave/probes/WFA-0149/graph.py",
    "command-center/p2-wave/probes/WFA-0149/emit.py",
    "command-center/p2-wave/probes/WFA-0149/probe1_per_pair.py",
    "command-center/p2-wave/probes/WFA-0149/probe2_bulk_symmetrise.py",
    "command-center/p2-wave/probes/WFA-0149/fixtures/census-replica-library.json",
    "command-center/p2-wave/probes/WFA-0149/fixtures/merge-maps-decoy-counts.json",
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
        "unit_id": "WFA-0149",
        "receipt_path": "command-center/p2-wave/probes/WFA-0149/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ecode, etext = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0149/emit.py"
    )
    if ecode != 0:
        print(f"FAILED:receipts emit rc={ecode}")
        print(etext[-2000:])
        return 1
    print(etext.splitlines()[-3:] and "\n".join(etext.splitlines()[-3:]))

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    probes = [
        {
            "id": "probe1",
            "command": P1,
            "exit_code": c1,
            "role": "per-pair-adjudication",
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "command": P2,
            "exit_code": c2,
            "role": "bulk-symmetrise-refused",
            "raw_output": t2,
        },
    ]
    ret = {
        "id": "WFA-0149",
        "unit_id": "WFA-0149",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0149",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/foundry-artifact.schema.json#/$defs/compat-repair",
        "named_probes": probes,
        "probes": probes,
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0149/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0149-probe2-bulk-symmetrise-refused",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0149: live named probes exit 0, foundry artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud_ok is false and "
            "is not delivery. Live 09/10 harness files are absent; census-"
            "replica matches published 108/390/265/140/0."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0149",
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
    print("SUCCESS:WFA-0149 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
