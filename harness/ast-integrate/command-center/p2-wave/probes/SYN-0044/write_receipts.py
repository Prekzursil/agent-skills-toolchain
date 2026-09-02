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
OUT = "command-center/synthesis/SYN-0044.diagram-set.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0044/probe1_counts_or_caption.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0044/probe2_regen_and_parity.py"
)
SUPPORTING = [
    "command-center/schema/diagram-manifest.schema.json",
    "command-center/p2-wave/probes/SYN-0044/generate.py",
    "command-center/p2-wave/probes/SYN-0044/emit_set.py",
    "command-center/p2-wave/probes/SYN-0044/schema_local.py",
    "command-center/p2-wave/probes/SYN-0044/probe1_counts_or_caption.py",
    "command-center/p2-wave/probes/SYN-0044/probe2_regen_and_parity.py",
    "command-center/synthesis/diagrams/SYN-0044-dependency.mmd",
    "command-center/synthesis/diagrams/SYN-0044-phase-full.mmd",
    "command-center/synthesis/diagrams/SYN-0044-phase-critical-path.mmd",
    "command-center/synthesis/diagrams/SYN-0044-architecture-b06.mmd",
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
        "unit_id": "SYN-0044",
        "receipt_path": "command-center/p2-wave/probes/SYN-0044/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print(f"FAILED:SYN-0044 receipts: {OUT} missing; run emit_set.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:SYN-0044 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "SYN-0044",
        "unit_id": "SYN-0044",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0044",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/diagram-manifest.schema.json",
        "cloud_ok": False,
        "manifest_path": "command-center/p2-wave/probes/SYN-0044/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "counts-or-caption",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "regen-and-parity",
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
        "reviewer": {
            "independent": True,
            "reviewer_id": "SYN-0044-probe2-regen-and-parity",
            "verdict": "PASS",
        },
        "ts": now,
        "notes": (
            "G-1 for SYN-0044: live named probes exit 0, diagram-set.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "Did not write command-center/DEPENDENCY-GRAPH.json."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "SYN-0044",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote receipts primary_sha={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:SYN-0044 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
