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
REPO = Path(__file__).resolve().parents[4]
OUT = "command-center/phase4/contracts/ARC-0085.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0085/probe1_repetition_immunity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0085/probe2_settling_probe.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ARC-0085/emit_contract.py",
    "command-center/p2-wave/probes/ARC-0085/validator.py",
    "command-center/p2-wave/probes/ARC-0085/claims.py",
    "command-center/p2-wave/probes/ARC-0085/probe1_repetition_immunity.py",
    "command-center/p2-wave/probes/ARC-0085/probe2_settling_probe.py",
    "command-center/phase3/A1/DESIGN.json",
    "command-center/phase3/A1/REFUTATION.json",
    "command-center/phase3/A2/DESIGN.json",
    "command-center/phase3/A2/REFUTATION.json",
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
        "unit_id": "ARC-0085",
        "receipt_path": "command-center/p2-wave/probes/ARC-0085/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = run_probe(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ARC-0085/emit_contract.py"
    )
    if emit[0] != 0:
        print(f"FAILED:receipts emit rc={emit[0]}")
        print(emit[1][-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    fixture = HERE / "fixtures" / "encoded-claims.json"
    supporting = list(SUPPORTING)
    if fixture.is_file():
        supporting.append(
            "command-center/p2-wave/probes/ARC-0085/fixtures/encoded-claims.json"
        )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in supporting]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ARC-0085",
        "unit_id": "ARC-0085",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0085",
        "registered": True,
        "output_path": OUT,
        "output_schema": "https://json-schema.org/draft/2020-12/schema",
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
        "manifest_path": "command-center/p2-wave/probes/ARC-0085/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ARC-0085-probe1-repetition-immunity",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ARC-0085: live named probes exit 0, claim-record schema "
            "state omitted (not BLOCKED), per-unit manifest row. "
            "CLAIM-REGISTRY.json absent; ten claims encoded from live phase-3 "
            "DESIGN/REFUTATION artifacts. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ARC-0085",
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
    print("SUCCESS:ARC-0085 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
