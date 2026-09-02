#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/BLD-0049.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0049/probe1_census_anchors.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0049/probe2_canary.py"
)
SUPPORTING = [
    "command-center/schema/threat-coverage-matrix.schema.json",
    "command-center/p2-wave/probes/BLD-0049/fence.py",
    "command-center/p2-wave/probes/BLD-0049/assemble.py",
    "command-center/p2-wave/probes/BLD-0049/executor.py",
    "command-center/p2-wave/probes/BLD-0049/census.py",
    "command-center/p2-wave/probes/BLD-0049/production.py",
    "command-center/p2-wave/probes/BLD-0049/canary.py",
    "command-center/p2-wave/probes/BLD-0049/probe1_census_anchors.py",
    "command-center/p2-wave/probes/BLD-0049/probe2_canary.py",
    "command-center/p2-wave/probes/ARC-0010/generator.py",
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
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "BLD-0049",
        "receipt_path": "command-center/p2-wave/probes/BLD-0049/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = HERE / "emit_receipt.py"
    c0, t0 = run_probe(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {emit.relative_to(REPO).as_posix()}")
    if c0 != 0:
        print(t0[-3000:])
        print("FAILED:BLD-0049 write_receipts emit")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "BLD-0049",
        "unit_id": "BLD-0049",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0049",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/threat-coverage-matrix.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/BLD-0049/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "BLD-0049-probe2-encoded-canary",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for BLD-0049: live named probes exit 0, receipts/BLD-0049.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No A2/ADV rebuild; production concatenators "
            "remain UNFENCED and are reported as such."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0049",
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
    print("SUCCESS:BLD-0049 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
